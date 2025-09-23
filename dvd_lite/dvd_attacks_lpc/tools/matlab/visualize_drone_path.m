% visualize_drone_path.m (v15.0 - Dynamic Viewport Tracking)
% 모든 텔레메트리 데이터를 활용하여 드론의 3D 경로와 자세(Attitude)를 완벽하게 시각화합니다.
% 드론을 중심으로 축이 동적으로 움직이는 고급 카메라 추적 기능을 구현한 최종 버전입니다.

function visualize_drone_path()
    % --- 설정 ---
    projectBasePath = '/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc'; % 사용자 환경에 맞게 수정
    physLogPath = fullfile(projectBasePath, 'bus', 'bus_dvd.log');
    cyberLogPath = fullfile(projectBasePath, 'bus', 'bus.log');

    updateInterval = 0.05; % 20Hz 갱신 (20fps)
    pathDuration_s = 5;    % 최근 5초간의 경로를 표시 (추적 성능을 위해 약간 줄임)
    earthRadius_m = 6371000; % 지구 반지름
    
    % --- 새로운 기능 설정 ---
    enableCameraTracking = true; % true로 설정하면 카메라가 드론을 자동으로 따라갑니다.
    viewRange = 50; % 드론 중심의 시야 범위 (미터), 이 값이 클수록 넓게 보임

    % --- 그래픽 및 데이터 초기화 ---
    fprintf('>> 통합 사이버/물리 시각화 대시보드 (v15.0 - Dynamic Viewport) 시작...\n');
    
    fig = figure('Name', '실시간 통합 시각화 대시보드', 'NumberTitle', 'off', 'Color', '#1e1e1e', 'Position', [100, 100, 1800, 800]);
    
    ax3D = subplot(1, 2, 1, 'Parent', fig);
    axLog = subplot(1, 2, 2, 'Parent', fig);

    % --- 3D 플롯 설정 ---
    set(ax3D, 'Color', '#282c34', 'GridColor', '#555', 'XColor', 'w', 'YColor', 'w', 'ZColor', 'w');
    hold(ax3D, 'on'); 
    grid(ax3D, 'on'); 
    axis(ax3D, 'equal'); 
    view(ax3D, 45, 25);
    
    xlabel(ax3D, 'X (m)'); 
    ylabel(ax3D, 'Y (m)'); 
    zlabel(ax3D, '고도 (m)');
    
    pathPlot = plot3(ax3D, NaN, NaN, NaN, '-c', 'LineWidth', 2.5, 'DisplayName', 'Drone Path');
    infoText = text(ax3D, 0, 0, 0, '', 'FontSize', 11, 'Color', 'white', 'FontWeight', 'bold', 'VerticalAlignment', 'bottom', 'FontName', 'Monospaced');
    eventMarkers = plot3(ax3D, NaN, NaN, NaN, 'yo', 'MarkerFaceColor', 'y', 'MarkerSize', 10, 'DisplayName', 'Cyber Events');
    
    droneTransform = hgtransform('Parent', ax3D);
    [propellerHandles, ~] = createDroneModel(droneTransform);
    
    % --- 이벤트 로그 패널 설정 ---
    set(axLog, 'Color', 'k', 'XColor', 'k', 'YColor', 'k', 'XTick', [], 'YTick', []);
    title(axLog, '통합 이벤트 로그 (bus.log)', 'Color', 'w', 'FontSize', 14);
    logTextHandles = gobjects(15, 1);
    for i = 1:15
        logTextHandles(i) = text(axLog, 0.05, 1 - (i * 0.06), '', 'Color', 'w', 'FontSize', 10, 'Interpreter', 'none', 'FontName', 'Monospaced');
    end
    
    pathData = []; 
    origin = []; 
    lastPhysPos = 0;
    cyberLogBuffer = {}; 
    lastCyberPos = 0;
    eventPositions = [];
    propRotation = 0;

    % --- 메인 루프 ---
    while ishandle(fig)
        [pathData, origin, lastPhysPos, lastLogData, ~] = updatePhysicalPlot(physLogPath, lastPhysPos, pathData, origin, earthRadius_m, pathDuration_s);
        [cyberLogBuffer, lastCyberPos, newEvent] = updateCyberLog(cyberLogPath, lastCyberPos, cyberLogBuffer);

        if ~isempty(lastLogData)
            if newEvent && ~isempty(pathData)
                eventPositions(end+1, :) = pathData(end, 2:4);
            end
            update3DGraphics(ax3D, pathPlot, droneTransform, infoText, eventMarkers, pathData, lastLogData, eventPositions, propellerHandles, propRotation, enableCameraTracking, viewRange);
        end
        
        updateLogPanel(logTextHandles, cyberLogBuffer);

        propRotation = propRotation + 0.5; 
        
        pause(updateInterval);
        drawnow limitrate;
    end
    fprintf('>> 시각화 스크립트를 종료합니다.\n');
end

% --- 헬퍼 함수들 ---

function [pathData, origin, lastPos, lastLogData, newEvent] = updatePhysicalPlot(logPath, lastPos, pathData, origin, R, duration)
    lastLogData = [];
    newEvent = false;
    newLines = readNewLines(logPath, lastPos);
    if isempty(newLines), return; end
    lastPos = newLines.newPos;
    
    tempLogData = [];
    for i = 1:length(newLines.lines)
        [logData, success] = parsePhysicalLog(newLines.lines{i});
        if ~success, continue; end
        
        if isfield(logData, 'type') && strcmp(logData.type, 'drone_state_detailed')
            tempLogData = logData;
            
            if isempty(origin) && isfield(logData, 'lat') && ~isnan(logData.lat)
                origin.lat = logData.lat; 
                origin.lon = logData.lon; 
                origin.alt = logData.alt_m;
            end
            
            if ~isempty(origin)
                x = R * (logData.lon - origin.lon) * cosd(origin.lat);
                y = R * (logData.lat - origin.lat);
                z = logData.alt_m - origin.alt;
                
                pathData(end+1, :) = [logData.timestamp, x, y, z];
            end
        end
    end
    
    if ~isempty(tempLogData)
        lastLogData = tempLogData;
    end
    
    if ~isempty(pathData)
        latestTimestamp = pathData(end, 1);
        pathData(pathData(:, 1) < (latestTimestamp - duration), :) = [];
    end
end

function update3DGraphics(ax, pathPlot, droneTransform, infoText, eventMarkers, pathData, lastLogData, eventPositions, propellerHandles, propRotation, enableCameraTracking, viewRange)
    if isempty(pathData), return; end
    lastX = pathData(end, 2); lastY = pathData(end, 3); lastZ = pathData(end, 4);
    
    set(pathPlot, 'XData', pathData(:, 2), 'YData', pathData(:, 3), 'ZData', pathData(:, 4));
    if ~isempty(eventPositions)
        set(eventMarkers, 'XData', eventPositions(:,1), 'YData', eventPositions(:,2), 'ZData', eventPositions(:,3));
    end
    
    translation = makehgtform('translate', [lastX, lastY, lastZ]);
    yawRotation = makehgtform('zrotate', deg2rad(-lastLogData.yaw_deg));
    pitchRotation = makehgtform('yrotate', deg2rad(lastLogData.pitch_deg));
    rollRotation = makehgtform('xrotate', deg2rad(lastLogData.roll_deg));
    
    set(droneTransform, 'Matrix', translation * yawRotation * pitchRotation * rollRotation);
    
    for i = 1:4
        prop_rot = makehgtform('zrotate', propRotation * (mod(i,2)*2-1));
        set(propellerHandles(i), 'Matrix', prop_rot);
    end

    armedStr = 'DISARMED';
    if lastLogData.armed, armedStr = 'ARMED!!'; end
    
    infoContent = sprintf([...
        'Arm: %-9s | Mode: %-10s | Bat: %3d%%\n' ...
        'Lat: %-9.6f | Lon: %-9.6f\n' ...
        'Alt(Abs): %-7.1fm | Alt(Rel): %-7.1fm\n' ...
        'Vel (X,Y,Z): %-5.1f, %-5.1f, %-5.1f m/s\n' ...
        'Gnd Spd: %-5.1f m/s | Heading: %3d deg\n' ...
        'Throttle: %3d%%     | CPU Load: %5.1f%%' ...
        ], ...
        armedStr, lastLogData.mode, lastLogData.battery_pct, ...
        lastLogData.lat, lastLogData.lon, ...
        lastLogData.alt_m, lastLogData.relative_alt_m, ...
        lastLogData.vx, lastLogData.vy, lastLogData.vz, ...
        lastLogData.groundspeed_ms, lastLogData.heading_deg, ...
        lastLogData.throttle_pct, lastLogData.cpu_load_pct);
        
    set(infoText, 'Position', [lastX, lastY, lastZ + max(12, lastZ*0.1)], 'String', infoContent);
    title(ax, sprintf('물리적 상태 | 고도: %.1f m | (X,Y,Z): (%.1f, %.1f, %.1f)', lastZ, lastX, lastY, lastZ), 'Color', 'w');
    
    % <<< 동적 뷰포트 카메라 추적 로직
    if enableCameraTracking
        halfRange = viewRange / 2;
        set(ax, 'XLim', [lastX - halfRange, lastX + halfRange]);
        set(ax, 'YLim', [lastY - halfRange, lastY + halfRange]);
        set(ax, 'ZLim', [max(0, lastZ - halfRange), lastZ + halfRange]); % Z축은 0 이하로 내려가지 않도록
        
        % 시점 각도는 유지
        [az, el] = view(ax);
        view(ax, az, el);
    end
end

function [propellerTransforms, bodyHandle] = createDroneModel(parent)
    [x, y, z] = cylinder([0.2 0.5 0.4 0.1 0], 20);
    bodyHandle = surf(x*0.5, y*0.5, z-0.5, 'Parent', parent, 'FaceColor', '#555', 'EdgeColor', 'none');

    patch('Parent', parent, 'Vertices', [-1.5 0 0; 1.5 0 0; 1.5 0 0; -1.5 0 0], 'Faces', [1 2 3 4], 'EdgeColor', '#777', 'LineWidth', 5);
    patch('Parent', parent, 'Vertices', [0 -1.5 0; 0 1.5 0; 0 1.5 0; 0 -1.5 0], 'Faces', [1 2 3 4], 'EdgeColor', '#777', 'LineWidth', 5);
    
    prop_positions = [1.2 0 0.1; -1.2 0 0.1; 0 1.2 0.1; 0 -1.2 0.1];
    colors = {'r'; '#48dbfb'; '#48dbfb'; '#48dbfb'}; 
    propellerTransforms = gobjects(4,1);
    for i = 1:4
        prop_parent = hgtransform('Parent', parent, 'Matrix', makehgtform('translate', prop_positions(i,:)));
        propellerTransforms(i) = hgtransform('Parent', prop_parent);
        
        patch('Parent', propellerTransforms(i), 'Vertices', [-0.4 0.05 0; 0.4 0.05 0; 0.4 -0.05 0; -0.4 -0.05 0], 'Faces', [1 2 3 4], 'FaceColor', colors{i});
        patch('Parent', propellerTransforms(i), 'Vertices', [-0.05 0.4 0; 0.05 0.4 0; 0.05 -0.4 0; -0.05 -0.4 0], 'Faces', [1 2 3 4], 'FaceColor', colors{i});
    end
end

function [result, success] = parsePhysicalLog(jsonStr)
    result = struct(); 
    success = false;
    try
        logData = jsondecode(jsonStr);
        result.timestamp = logData.ts;
        result.type = logData.type;
        
        if strcmp(logData.type, 'drone_state_detailed')
            data = logData.data;
            result.pitch_deg = get_field(data, 'pitch_deg', 0);
            result.roll_deg = get_field(data, 'roll_deg', 0);
            result.yaw_deg = get_field(data, 'yaw_deg', 0);
            result.lat = get_field(data, 'lat', NaN);
            result.lon = get_field(data, 'lon', NaN);
            result.alt_m = get_field(data, 'alt_m', NaN);
            result.relative_alt_m = get_field(data, 'relative_alt_m', NaN);
            result.vx = get_field(data, 'vx', NaN);
            result.vy = get_field(data, 'vy', NaN);
            result.vz = get_field(data, 'vz', NaN);
            result.cpu_load_pct = get_field(data, 'cpu_load_pct', NaN);
            result.errors_count1 = get_field(data, 'errors_count1', 0);
            result.errors_count2 = get_field(data, 'errors_count2', 0);
            result.groundspeed_ms = get_field(data, 'groundspeed_ms', NaN);
            result.heading_deg = get_field(data, 'heading_deg', 0);
            result.throttle_pct = get_field(data, 'throttle_pct', 0);
            result.battery_v = get_field(data, 'battery_v', NaN);
            result.battery_pct = get_field(data, 'battery_pct', -1);
            result.armed = get_field(data, 'armed', false);
            result.mode = get_field(data, 'mode', 'UNKNOWN');
            result.system_status = get_field(data, 'system_status', 'UNKNOWN');
            
            if ~isnan(result.lat), success = true; end
        else
            success = true;
        end
    catch
        success = false;
    end
end

function val = get_field(struct_data, fieldname, default_val)
    if isfield(struct_data, fieldname) && ~isempty(struct_data.(fieldname))
        val = struct_data.(fieldname);
    else
        val = default_val;
    end
end

function [logBuffer, lastPos, newEvent] = updateCyberLog(logPath, lastPos, logBuffer)
    newEvent = false;
    newLines = readNewLines(logPath, lastPos);
    if isempty(newLines), return; end
    lastPos = newLines.newPos;
    
    for i = 1:length(newLines.lines)
        try
            event = jsondecode(newLines.lines{i});
            if isfield(event, 'type') && (contains(event.type, 'attack') || contains(event.type, 'mtd'))
                newEvent = true;
            end
            summary = formatCyberEvent(event);
            logBuffer{end+1} = summary;
        catch
        end
    end
    
    if length(logBuffer) > 15, logBuffer = logBuffer(end-14:end); end
end

function summary = formatCyberEvent(event)
    ts = datetime(event.ts, 'ConvertFrom', 'posixtime', 'Format', 'HH:mm:ss.SSS');
    type = get_field(event, 'type', 'unknown_event');
    data = get_field(event, 'data', struct());
    summary = sprintf('[%s] %s', datestr(ts, 'HH:MM:SS.FFF'), strrep(type, '_', ' '));

    if isfield(data, 'attack'), summary = [summary, sprintf(' | Attack: %s', data.attack)]; end
    if isfield(data, 'target'), summary = [summary, sprintf(' | Target: %s', data.target)]; end
    if isfield(data, 'strategy'), summary = [summary, sprintf(' | MTD: %s -> %s', data.strategy, data.details)]; end
    if isfield(data, 'predicted_category'), summary = [summary, sprintf(' | AI: %s (%.1f%%)', data.predicted_category, data.confidence*100)]; end
end

function updateLogPanel(textHandles, logBuffer)
    for i = 1:length(textHandles)
        if i <= length(logBuffer)
            logLine = logBuffer{end-i+1};
            color = 'w';
            if contains(logLine, 'Attack', 'IgnoreCase', true), color = '#ff6b6b'; end
            if contains(logLine, 'MTD', 'IgnoreCase', true), color = '#48dbfb'; end
            if contains(logLine, 'AI', 'IgnoreCase', true), color = '#feca57'; end
            if contains(logLine, 'RECON', 'IgnoreCase', true), color = '#ff9f43'; end
            set(textHandles(i), 'String', ['> ' logLine], 'Color', color);
        else
            set(textHandles(i), 'String', '');
        end
    end
end

function newLines = readNewLines(logPath, lastPos)
    newLines = [];
    file_info = dir(logPath);
    if isempty(file_info) || file_info.bytes <= lastPos, return; end
    
    try
        fid = fopen(logPath, 'r', 'n', 'UTF-8');
        if fid == -1, return; end
        fseek(fid, lastPos, 'bof');
        lines = {};
        while ~feof(fid)
            line = fgetl(fid);
            if ischar(line) && ~isempty(line), lines{end+1} = line; end
        end
        newPos = ftell(fid);
        fclose(fid);
        newLines.lines = lines;
        newLines.newPos = newPos;
    catch
    end
end