import pandas as pd
import json
import logging
import time
import os
from datetime import datetime
from dataset_manager import DatasetManager # Assuming DatasetManager handles saving
from watchdog.observers import Observer # Added for streaming example
from watchdog.events import FileSystemEventHandler # Added for streaming example

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DataBuilder")

# --- 경로 설정 ---
# 이 스크립트 파일의 위치를 기준으로 상대 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 기본값 설정 (명령행 인수로 덮어쓸 수 있음)
DEFAULT_BUS_LOG_PATH = os.path.abspath(os.path.join(BASE_DIR, '../bus.log')) # Use absolute path
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, './processed_data')) # Use absolute path
DEFAULT_MAPPING_FILE = os.path.abspath(os.path.join(BASE_DIR, 'event_mapping.json')) # Use absolute path

class DataBuilder:
    def __init__(self, bus_log_path=DEFAULT_BUS_LOG_PATH, output_dir=DEFAULT_OUTPUT_DIR, mapping_file=DEFAULT_MAPPING_FILE):
        self.bus_log_path = bus_log_path
        self.output_dir = output_dir
        self.dataset_manager = DatasetManager(output_dir) # DatasetManager needs absolute path
        self.event_mapping = {} # Initialize empty

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        try:
            with open(mapping_file, 'r') as f:
                self.event_mapping = json.load(f)
            logger.info(f"Loaded event mapping from {mapping_file}")
        except FileNotFoundError:
            logger.error(f"Event mapping file not found at {mapping_file}. Cannot automatically label attack data. Using empty mapping.")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {mapping_file}: {e}. Using empty mapping.")
        except Exception as e:
            logger.error(f"Unexpected error loading event mapping file {mapping_file}: {e}. Using empty mapping.")

        # For streaming: track last processed position/time
        self._last_file_position = 0
        self._last_log_timestamp = None # Optional: Use timestamp if seeking by position is unreliable

    def parse_log_entry(self, line):
        """Parses a single JSON entry from the bus log."""
        try:
            log_entry = json.loads(line)
            # Standardize timestamp parsing (handle potential errors)
            ts_str = log_entry.get('timestamp')
            if ts_str:
                 # Try ISO format with ZULU timezone first
                 try:
                     log_entry['timestamp'] = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                 except ValueError:
                     # Try other common formats if needed, or fallback
                     try:
                        # Example: Fallback to assuming local time if format differs
                        log_entry['timestamp'] = datetime.fromisoformat(ts_str)
                        logger.warning(f"Timestamp '{ts_str}' missing ZULU indicator, parsed as local time.")
                     except ValueError:
                        logger.error(f"Could not parse timestamp format: {ts_str}. Using current time.")
                        log_entry['timestamp'] = datetime.now() # Fallback
            else:
                 logger.warning("Log entry missing 'timestamp'. Using current time.")
                 log_entry['timestamp'] = datetime.now()
            return log_entry
        except json.JSONDecodeError:
            # Log potentially sensitive info at DEBUG level
            logger.debug(f"Skipping malformed JSON log entry: {line.strip()}")
            return None
        except Exception as e:
            logger.error(f"Error parsing log entry: {line.strip()} - Error: {e}")
            return None

    def extract_features(self, log_entry):
        """
        Extracts features from a parsed log entry. Enhanced based on monitor types.
        """
        features = {'timestamp': log_entry['timestamp']} # Always include timestamp
        source = log_entry.get('source', 'unknown')
        event_type = log_entry.get('event_type', 'unknown')
        data = log_entry.get('data', {})

        # --- Feature Extraction Logic ---

        # Example 1: Network Traffic Monitor Data
        if source == 'network_traffic_monitor':
            # Basic connection info (consider anonymizing IPs if needed)
            features['net_protocol'] = data.get('protocol', 'unknown').lower() # e.g., 'tcp', 'udp', 'icmp'
            features['net_src_ip'] = data.get('src_ip')
            features['net_dst_ip'] = data.get('dst_ip')
            features['net_src_port'] = data.get('src_port')
            features['net_dst_port'] = data.get('dst_port')
            # Traffic volume stats
            features['net_packet_count'] = data.get('packet_count')
            features['net_total_bytes'] = data.get('total_bytes')
            # Packet size stats (handle potential missing keys)
            pkt_stats = data.get('packet_size_stats', {})
            features['net_pkt_size_avg'] = pkt_stats.get('avg')
            features['net_pkt_size_std'] = pkt_stats.get('std')
            features['net_pkt_size_min'] = pkt_stats.get('min')
            features['net_pkt_size_max'] = pkt_stats.get('max')
            # Flow duration/frequency (if provided by monitor)
            features['net_flow_duration_sec'] = data.get('flow_duration_sec')
            features['net_flow_bytes_per_sec'] = data.get('flow_bytes_per_sec')
            # Advanced features (hypothetical - need implementation in monitor)
            features['net_conn_freq'] = data.get('conn_frequency') # How often this pair communicates
            features['net_payload_entropy'] = data.get('payload_entropy') # Randomness of payload

        # Example 2: Telemetry Monitor Data
        elif source == 'dvd_telemetry_monitor':
            if event_type == 'mavlink_message':
                 # General MAVLink info
                 features['mav_msg_id'] = data.get('msg_id')
                 features['mav_msg_name'] = data.get('msg_name', 'UNKNOWN').upper()
                 features['mav_sys_id'] = data.get('sys_id')
                 features['mav_comp_id'] = data.get('comp_id')
                 # Payload features (extract important fields per message type)
                 payload = data.get('payload', {})
                 msg_name = features['mav_msg_name']

                 if msg_name == 'HEARTBEAT':
                     features['mav_hb_type'] = payload.get('type')
                     features['mav_hb_autopilot'] = payload.get('autopilot')
                     features['mav_hb_status'] = payload.get('system_status')
                 elif msg_name == 'GLOBAL_POSITION_INT':
                     features['mav_gps_lat'] = payload.get('lat')
                     features['mav_gps_lon'] = payload.get('lon')
                     features['mav_gps_alt'] = payload.get('alt') # Altitude MSL
                     features['mav_gps_rel_alt'] = payload.get('relative_alt') # Altitude relative to home
                     features['mav_gps_vx'] = payload.get('vx') # Ground speed N/S
                     features['mav_gps_vy'] = payload.get('vy') # Ground speed E/W
                     features['mav_gps_vz'] = payload.get('vz') # Ground speed Dwon
                     features['mav_gps_hdg'] = payload.get('hdg') # Heading
                 elif msg_name == 'ATTITUDE':
                     features['mav_att_roll'] = payload.get('roll')
                     features['mav_att_pitch'] = payload.get('pitch')
                     features['mav_att_yaw'] = payload.get('yaw')
                     features['mav_att_rollspeed'] = payload.get('rollspeed')
                 elif msg_name == 'SYS_STATUS':
                     features['mav_sys_voltage'] = payload.get('voltage_battery')
                     features['mav_sys_current'] = payload.get('current_battery')
                     features['mav_sys_load'] = payload.get('load')
                     features['mav_sys_errors'] = payload.get('errors_count1') # Example error count

        # Example 3: Container Monitor Data
        elif source == 'dvd_container_monitor':
            # Target container info (consider mapping ID/name to roles if useful)
            # features['cont_id'] = data.get('container_id') # Maybe less useful than name
            features['cont_name'] = data.get('container_name')
            # Resource usage
            features['cont_cpu_usage_pct'] = data.get('cpu_usage') # Assuming percentage
            features['cont_mem_usage_mb'] = data.get('memory_usage') # Assuming MB
            features['cont_mem_limit_mb'] = data.get('memory_limit')
            features['cont_mem_pct'] = data.get('memory_percent')
            # Network I/O
            features['cont_net_rx_bytes'] = data.get('network_rx_bytes')
            features['cont_net_tx_bytes'] = data.get('network_tx_bytes')
            # Disk I/O (if available)
            features['cont_disk_read_bytes'] = data.get('disk_read_bytes')
            features['cont_disk_write_bytes'] = data.get('disk_write_bytes')

        # Example 4: QoS Monitor Data
        elif source == 'qos_monitor':
            # Network quality metrics between specific points (e.g., GCS <-> Drone)
            features['qos_target'] = data.get('target_pair', 'unknown') # e.g., 'gcs_drone'
            features['qos_latency_ms'] = data.get('latency_ms')
            features['qos_jitter_ms'] = data.get('jitter_ms')
            features['qos_packet_loss_pct'] = data.get('packet_loss_rate') # Assuming rate is 0-1 or 0-100
            features['qos_throughput_kbps'] = data.get('throughput_kbps') # If measured

        # Example 5: System Event Monitor Data
        elif source == 'system_event_monitor':
             # OS-level or application-level events
             features['sys_event_type'] = data.get('type') # e.g., 'login_failed', 'file_access', 'process_start'
             features['sys_event_user'] = data.get('username', 'unknown')
             features['sys_event_process'] = data.get('process_name')
             features['sys_event_path'] = data.get('file_path') # e.g., for file access events
             features['sys_event_success'] = data.get('success') # Boolean: did the event succeed?

        # Example 6: Attack Orchestrator Events for Labeling
        elif source == 'attack_orchestrator':
             if event_type == 'attack_started':
                 attack_name = data.get('attack_name')
                 # Map attack name to a numerical label using event_mapping
                 label = self.event_mapping.get(attack_name, 0) # Default to 0 (normal) if not found
                 if label == 0 and attack_name: # Log warning if attack started but not in mapping
                      logger.warning(f"Attack '{attack_name}' started but not found in event mapping. Assigning label 0.")
                 features['label'] = label
                 features['attack_in_progress'] = 1 # Flag indicating an attack is active during this log entry
             elif event_type == 'attack_stopped':
                 # When attack stops, mark as not in progress and reset label to normal
                 features['attack_in_progress'] = 0
                 features['label'] = 0 # Assume normal state after attack stops (adjust if needing post-attack analysis)

        # Fallback/Default features (Legacy or Uncategorized)
        else:
             # Basic MAVLink parsing (can be removed if fully covered by telemetry monitor)
             if log_entry.get('message_type') == 'MAVLink' and 'mav_msg_id' not in features:
                 features['mav_msg_id'] = log_entry.get('msgid') # Use different prefix to avoid clash
                 logger.debug("Processed legacy MAVLink entry.")
             # Basic Network Scan parsing (can be removed if covered by network monitor)
             elif 'scan detected' in log_entry.get('message', '').lower():
                 features['scan_detected'] = 1
                 logger.debug("Processed legacy scan detection entry.")
             # Add other specific fallback parsing if necessary

        # --- Default Values & Type Consistency ---
        # Ensure label and attack_in_progress always exist
        features.setdefault('label', 0)
        features.setdefault('attack_in_progress', 0)

        # Ensure numeric features have a consistent type (e.g., float)
        # Add more features to this list as needed
        numeric_cols = [
            'net_src_port', 'net_dst_port', 'net_packet_count', 'net_total_bytes',
            'net_pkt_size_avg', 'net_pkt_size_std', 'net_pkt_size_min', 'net_pkt_size_max',
            'net_flow_duration_sec', 'net_flow_bytes_per_sec', 'net_conn_freq', 'net_payload_entropy',
            'mav_msg_id', 'mav_sys_id', 'mav_comp_id', 'mav_hb_type', 'mav_hb_autopilot', 'mav_hb_status',
            'mav_gps_lat', 'mav_gps_lon', 'mav_gps_alt', 'mav_gps_rel_alt', 'mav_gps_vx', 'mav_gps_vy', 'mav_gps_vz', 'mav_gps_hdg',
            'mav_att_roll', 'mav_att_pitch', 'mav_att_yaw', 'mav_att_rollspeed',
            'mav_sys_voltage', 'mav_sys_current', 'mav_sys_load', 'mav_sys_errors',
            'cont_cpu_usage_pct', 'cont_mem_usage_mb', 'cont_mem_limit_mb', 'cont_mem_pct',
            'cont_net_rx_bytes', 'cont_net_tx_bytes', 'cont_disk_read_bytes', 'cont_disk_write_bytes',
            'qos_latency_ms', 'qos_jitter_ms', 'qos_packet_loss_pct', 'qos_throughput_kbps',
            'scan_detected', 'label', 'attack_in_progress'
        ]
        for col in numeric_cols:
            if col in features:
                 try:
                     # Attempt conversion to float, handle None or non-convertible values
                     features[col] = float(features[col]) if features[col] is not None else None # Keep None for now, handle in fillna
                 except (ValueError, TypeError):
                     logger.warning(f"Could not convert feature '{col}' value '{features[col]}' to float. Setting to None.")
                     features[col] = None # Set invalid conversions to None

        return features

    def _post_process_dataframe(self, df):
        """Applies post-processing steps like handling missing values and categorical data."""
        if df.empty:
            return df

        logger.info(f"Shape before post-processing: {df.shape}")

        # --- Handle Missing Values (More Specific) ---
        # Strategy: Fill counts, bytes, sizes, progress flags with 0. Fill ports with -1. Fill stats (avg, std, etc.) with 0 or mean/median.
        fill_zeros = [col for col in df.columns if 'count' in col or 'bytes' in col or 'size' in col or '_id' in col or '_status' in col or '_type' in col or 'progress' in col or 'detected' in col]
        fill_neg_one = [col for col in df.columns if 'port' in col]
        # Fill remaining numeric NaNs (like stats, GPS, attitude, QoS metrics) with 0 for simplicity,
        # but consider using df[col].mean() or df[col].median() for better results in training.
        remaining_numeric = df.select_dtypes(include='number').columns.difference(['timestamp', 'label'] + fill_zeros + fill_neg_one)

        for col in fill_zeros:
            if col in df.columns: df[col] = df[col].fillna(0)
        for col in fill_neg_one:
            if col in df.columns: df[col] = df[col].fillna(-1)
        for col in remaining_numeric:
             if col in df.columns:
                 # Option 1: Fill with 0
                 df[col] = df[col].fillna(0)
                 # Option 2: Fill with mean (uncomment to use)
                 # if pd.api.types.is_numeric_dtype(df[col]) and df[col].isnull().any():
                 #     mean_val = df[col].mean()
                 #     df[col] = df[col].fillna(mean_val)
                 #     logger.debug(f"Filled NaNs in {col} with mean ({mean_val})")


        # --- Handle Categorical Features ---
        # Example: One-hot encode protocol (limited cardinality)
        if 'net_protocol' in df.columns:
            logger.debug("Applying one-hot encoding to 'net_protocol'.")
            try:
                # fillna needed before get_dummies if protocol can be NaN
                df['net_protocol'] = df['net_protocol'].fillna('unknown')
                df = pd.get_dummies(df, columns=['net_protocol'], prefix='proto', dummy_na=False)
            except Exception as e:
                 logger.error(f"Failed to one-hot encode 'net_protocol': {e}")


        # Example: IP Addresses (High Cardinality - Consider other methods)
        # One-hot encoding IPs is usually infeasible. Alternatives:
        # 1. Frequency encoding
        # 2. Target encoding (if labels are available)
        # 3. Hashing trick
        # 4. Embedding layers (in neural networks)
        # 5. Extract features (e.g., is private IP, part of subnet) - Often preferred
        ip_cols = [col for col in df.columns if '_ip' in col]
        if ip_cols:
             logger.warning(f"IP address columns {ip_cols} found. Consider specialized encoding (e.g., feature extraction, hashing) instead of one-hot encoding for production models.")
             # Example: Simple feature extraction - is private IP?
             # def is_private(ip):
             #     if not isinstance(ip, str): return 0
             #     try:
             #         parts = list(map(int, ip.split('.')))
             #         return (parts[0] == 10 or
             #                 (parts[0] == 172 and 16 <= parts[1] <= 31) or
             #                 (parts[0] == 192 and parts[1] == 168))
             #     except:
             #         return 0
             # for ip_col in ip_cols:
             #      if ip_col in df.columns: df[f'{ip_col}_is_private'] = df[ip_col].apply(is_private)


        # Example: MAVLink message names (Moderate cardinality)
        if 'mav_msg_name' in df.columns:
            logger.debug("Applying one-hot encoding to 'mav_msg_name'.")
            try:
                df['mav_msg_name'] = df['mav_msg_name'].fillna('UNKNOWN')
                # Limit cardinality if too many unique messages appear
                top_msg_names = df['mav_msg_name'].value_counts().nlargest(50).index # Keep top 50
                df['mav_msg_name'] = df['mav_msg_name'].where(df['mav_msg_name'].isin(top_msg_names), 'OTHER')
                df = pd.get_dummies(df, columns=['mav_msg_name'], prefix='mav_msg', dummy_na=False)
            except Exception as e:
                logger.error(f"Failed to one-hot encode 'mav_msg_name': {e}")


        # Drop original categorical columns if they were encoded and no longer needed
        # (pd.get_dummies usually handles this unless drop_first=False)
        # Be careful not to drop timestamp or label here

        # Ensure timestamp is suitable index if needed later (optional here)
        # df = df.set_index('timestamp').sort_index()

        logger.info(f"Shape after post-processing: {df.shape}")
        logger.info(f"Final columns: {df.columns.tolist()}")
        return df


    def process_logs_batch(self):
        """Processes the entire bus log file in batch mode."""
        extracted_data = []
        logging.info(f"Starting batch processing of log file: {self.bus_log_path}")
        try:
            with open(self.bus_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    log_entry = self.parse_log_entry(line)
                    if log_entry:
                        try:
                            features = self.extract_features(log_entry)
                            extracted_data.append(features)
                        except Exception as e_feat:
                            logger.error(f"Error extracting features from log entry {i+1}: {log_entry} - Error: {e_feat}", exc_info=True) # Log traceback
                    # Optional: Add progress logging for large files
                    # if (i + 1) % 10000 == 0:
                    #     logger.info(f"Processed {i+1} log lines...")

        except FileNotFoundError:
            logger.error(f"Log file not found: {self.bus_log_path}")
            return None
        except Exception as e:
            logger.error(f"An error occurred during log file reading: {e}", exc_info=True)
            return None

        if not extracted_data:
            logger.warning("No data extracted from the log file.")
            return None

        logging.info(f"Creating DataFrame from {len(extracted_data)} extracted records.")
        df = pd.DataFrame(extracted_data)

        # Apply post-processing
        df = self._post_process_dataframe(df)

        if df.empty:
             logger.warning("DataFrame is empty after post-processing.")
             return None

        # Save the processed data using DatasetManager
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"features_batch_{timestamp_str}.csv"
        try:
            self.dataset_manager.save_dataframe(df, output_filename)
            logger.info(f"Saved processed batch data to {os.path.join(self.output_dir, output_filename)}")
        except Exception as e:
            logger.error(f"Failed to save processed data: {e}", exc_info=True)

        return df

    # --- Streaming Implementation Example (using watchdog) ---
    def _process_new_log_lines(self):
        """Internal helper to process new lines since last check."""
        new_features_list = []
        try:
            with open(self.bus_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(self._last_file_position)
                for line in f:
                    log_entry = self.parse_log_entry(line)
                    if log_entry:
                        try:
                             features = self.extract_features(log_entry)
                             new_features_list.append(features)
                        except Exception as e:
                             logger.error(f"Streaming: Error extracting features: {e}", exc_info=True)
                # Update position for next read
                self._last_file_position = f.tell()
        except FileNotFoundError:
            logger.error(f"Streaming: Log file not found at {self.bus_log_path}")
            # Reset position? Or wait for file creation?
            self._last_file_position = 0
            return None
        except Exception as e:
            logger.error(f"Streaming: Error reading log file: {e}")
            return None # Indicate error

        if new_features_list:
            logger.info(f"Streaming: Processed {len(new_features_list)} new log entries.")
            df_new = pd.DataFrame(new_features_list)
            # Apply post-processing (might need adjustments for streaming context)
            df_processed = self._post_process_dataframe(df_new.copy()) # Process a copy

            if not df_processed.empty:
                # --- Actions for streaming data ---
                # 1. Append to a larger file/database
                # 2. Send to a prediction endpoint/model
                # 3. Update internal state for time-window features (more complex)
                # Example: Save incrementally (can be inefficient for many small updates)
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f") # Microseconds for uniqueness
                out_file = f"features_stream_{ts_str}.csv"
                try:
                    self.dataset_manager.save_dataframe(df_processed, out_file)
                    logger.debug(f"Saved streaming chunk: {out_file}")
                except Exception as e:
                     logger.error(f"Streaming: Failed to save data chunk: {e}")

                # Return the processed chunk for potential immediate use
                return df_processed
            else:
                 logger.debug("Streaming: New data chunk was empty after post-processing.")
                 return pd.DataFrame() # Return empty DataFrame

        return pd.DataFrame() # Return empty DataFrame if no new lines processed


    def process_logs_streaming(self):
        """
        Monitors the log file for changes and processes new lines.
        NOTE: Requires 'watchdog' library (`pip install watchdog`).
        This is a basic example; robust streaming often uses message queues.
        """
        logger.info(f"Starting streaming processing for log file: {self.bus_log_path}")
        logger.warning("Ensure 'watchdog' is installed (`pip install watchdog`) for streaming.")

        # Initial read of existing content
        logger.info("Performing initial read of existing log content...")
        self._last_file_position = 0 # Reset position for full initial read
        initial_df = self._process_new_log_lines()
        if initial_df is not None:
             logger.info(f"Initial read processed {len(initial_df)} entries.")
        else:
             logger.warning("Initial read failed or produced no data.")


        # Setup watchdog observer
        event_handler = LogFileHandler(self)
        observer = Observer()
        # Observe the directory containing the log file
        log_dir = os.path.dirname(self.bus_log_path)
        observer.schedule(event_handler, log_dir, recursive=False)
        observer.start()
        logger.info(f"Watching for changes in {log_dir} (specifically monitoring {os.path.basename(self.bus_log_path)})...")

        try:
            while True:
                # Keep the main thread alive, processing happens in the handler
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping streaming observer.")
            observer.stop()
        except Exception as e:
             logger.error(f"Streaming observer encountered an error: {e}", exc_info=True)
             observer.stop()

        observer.join()
        logger.info("Streaming processing stopped.")


class LogFileHandler(FileSystemEventHandler):
     """Handles file system events for the bus log file."""
     def __init__(self, data_builder_instance):
         self.builder = data_builder_instance
         self.log_filename = os.path.basename(data_builder_instance.bus_log_path)

     def on_modified(self, event):
         # Check if the modified file is the one we are monitoring
         if not event.is_directory and os.path.basename(event.src_path) == self.log_filename:
             logger.debug(f"Detected modification in {event.src_path}, processing new lines.")
             # Trigger processing of new lines
             processed_chunk = self.builder._process_new_log_lines()
             if processed_chunk is not None and not processed_chunk.empty:
                  # Placeholder: Trigger prediction or further action with processed_chunk
                  logger.debug(f"Streaming: Trigger action with {len(processed_chunk)} new processed records.")
                  pass


# Example Usage
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build features from bus log.")
    parser.add_argument("--mode", choices=['batch', 'stream'], default='batch', help="Processing mode: batch or stream.")
    parser.add_argument("--log-file", default=DEFAULT_BUS_LOG_PATH, help="Path to the bus log file.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory to save processed data.")
    parser.add_argument("--mapping-file", default=DEFAULT_MAPPING_FILE, help="Path to event mapping JSON file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG) # Set root logger level too
        logger.debug("Debug logging enabled.")

    # Create necessary directories and dummy files if they don't exist for the example
    os.makedirs(args.output_dir, exist_ok=True)
    if not os.path.exists(args.mapping_file):
        dummy_mapping = {"gps-spoofing": 1, "communication-link-flooding": 2, "mavlink-injection-attack": 3}
        try:
            with open(args.mapping_file, 'w') as f:
                json.dump(dummy_mapping, f, indent=4)
            logger.info(f"Created dummy mapping file: {args.mapping_file}")
        except IOError as e:
            logger.error(f"Could not create dummy mapping file: {e}")

    # Ensure log file exists, create if not (for testing)
    if not os.path.exists(args.log_file):
        logger.warning(f"Log file {args.log_file} not found. Creating empty file for testing.")
        try:
            open(args.log_file, 'a').close()
        except IOError as e:
            logger.error(f"Could not create log file {args.log_file}: {e}")
            # Exit if log file cannot be created/accessed
            exit(1)


    # Initialize DataBuilder with paths from args
    builder = DataBuilder(bus_log_path=args.log_file,
                          output_dir=args.output_dir,
                          mapping_file=args.mapping_file)

    if args.mode == 'batch':
        logger.info("Running in BATCH mode.")
        processed_df = builder.process_logs_batch()
        if processed_df is not None:
            logger.info("Batch log processing complete.")
            # Further steps like training can be initiated here
        else:
            logger.error("Batch log processing failed.")

    elif args.mode == 'stream':
        logger.info("Running in STREAM mode (Example implementation).")
        try:
             builder.process_logs_streaming()
        except ImportError:
             logger.error("Failed to run in stream mode: 'watchdog' library not found. Please install it (`pip install watchdog`).")
        except Exception as e:
             logger.error(f"An error occurred during streaming: {e}", exc_info=True)

