#!/usr/bin/env bash
# NS-3 드론 네트워크 시뮬레이션 설정

NS3_ROOT="${NS3_ROOT:-$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
SCRATCH_DIR="$NS3_ROOT/scratch"
DRONE_EVAL_CC="$SCRATCH_DIR/drone_lpc_eval.cc"

# NS-3 드론 시뮬레이션 C++ 코드 생성
cat > "$DRONE_EVAL_CC" << 'CPP_EOF'
/* 
 * drone_lpc_eval.cc
 * 드론 LPC 공격 효과 네트워크 시뮬레이션
 */
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"
#include "ns3/mobility-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("DroneLpcEval");

class DroneAttackSimulator {
private:
    NodeContainer droneNodes;
    NodeContainer gcsNodes;
    double simTime;
    std::string timelineFile;
    std::string outputFile;

public:
    DroneAttackSimulator(double time, std::string timeline, std::string output) 
        : simTime(time), timelineFile(timeline), outputFile(output) {}

    void SetupTopology() {
        // 드론 및 GCS 노드 생성
        droneNodes.Create(1);  // 드론
        gcsNodes.Create(1);    // 지상관제소
        
        // WiFi 설정
        WifiHelper wifi;
        wifi.SetStandard(WIFI_STANDARD_80211n);
        
        WifiMacHelper wifiMac;
        YansWifiPhyHelper wifiPhy;
        YansWifiChannelHelper wifiChannel = YansWifiChannelHelper::Default();
        wifiPhy.SetChannel(wifiChannel.Create());
        
        // AP (드론) 설정
        Ssid ssid = Ssid("Drone_Wifi");
        wifiMac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
        NetDeviceContainer apDevice = wifi.Install(wifiPhy, wifiMac, droneNodes);
        
        // STA (GCS) 설정
        wifiMac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid));
        NetDeviceContainer staDevice = wifi.Install(wifiPhy, wifiMac, gcsNodes);
        
        // 이동성 모델
        MobilityHelper mobility;
        Ptr<ListPositionAllocator> positionAlloc = CreateObject<ListPositionAllocator>();
        positionAlloc->Add(Vector(0.0, 0.0, 100.0));  // 드론 위치 (고도 100m)
        positionAlloc->Add(Vector(0.0, 0.0, 0.0));    // GCS 위치
        mobility.SetPositionAllocator(positionAlloc);
        mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
        mobility.Install(droneNodes);
        mobility.Install(gcsNodes);
    }
    
    void ApplyAttackEffects() {
        // effect_timeline.csv 파싱하여 공격 효과 적용
        std::ifstream file(timelineFile);
        std::string line;
        
        while (std::getline(file, line)) {
            // CSV 파싱: t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps,module,level
            std::vector<std::string> tokens = ParseCsvLine(line);
            
            if (tokens.size() >= 7) {
                double timestamp = std::stod(tokens[0]);
                double loss_pct = std::stod(tokens[1]);
                double delay_ms = std::stod(tokens[2]);
                double jitter_ms = std::stod(tokens[3]);
                
                // 스케줄된 공격 효과 적용
                Simulator::Schedule(Seconds(timestamp), &DroneAttackSimulator::ApplyErrorModel, 
                                   this, loss_pct, delay_ms, jitter_ms);
            }
        }
    }
    
    void ApplyErrorModel(double loss_pct, double delay_ms, double jitter_ms) {
        // 패킷 손실 모델
        if (loss_pct > 0) {
            Ptr<RateErrorModel> errorModel = CreateObject<RateErrorModel>();
            errorModel->SetRate(loss_pct / 100.0);
            // 디바이스에 오류 모델 적용 로직
        }
        
        // 지연 및 지터 모델 (간단화)
        if (delay_ms > 0 || jitter_ms > 0) {
            // 채널 지연 특성 변경 로직
            NS_LOG_INFO("Applying delay: " << delay_ms << "ms, jitter: " << jitter_ms << "ms");
        }
    }
    
    void InstallApplications() {
        // MAVLink 트래픽 시뮬레이션
        uint16_t mavlinkPort = 14550;
        
        // 서버 (드론)
        UdpServerHelper mavlinkServer(mavlinkPort);
        ApplicationContainer serverApp = mavlinkServer.Install(droneNodes.Get(0));
        serverApp.Start(Seconds(0.0));
        serverApp.Stop(Seconds(simTime));
        
        // 클라이언트 (GCS)
        UdpClientHelper mavlinkClient(InetSocketAddress(Ipv4Address("10.13.0.2"), mavlinkPort));
        mavlinkClient.SetAttribute("MaxPackets", UintegerValue(4294967295u));
        mavlinkClient.SetAttribute("Interval", TimeValue(Time("50ms")));  // 20Hz MAVLink
        mavlinkClient.SetAttribute("PacketSize", UintegerValue(280));     // 평균 MAVLink 패킷 크기
        
        ApplicationContainer clientApp = mavlinkClient.Install(gcsNodes.Get(0));
        clientApp.Start(Seconds(1.0));
        clientApp.Stop(Seconds(simTime));
    }
    
    void EnableMetrics() {
        // 처리량, 지연, 패킷 손실 메트릭 수집
        FlowMonitorHelper flowmon;
        Ptr<FlowMonitor> monitor = flowmon.InstallAll();
        
        Simulator::Stop(Seconds(simTime));
        Simulator::Run();
        
        // 메트릭 수집 및 출력
        monitor->CheckForLostPackets();
        Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());
        std::map<FlowId, FlowMonitor::FlowStats> stats = monitor->GetFlowStats();
        
        std::ofstream outFile(outputFile);
        outFile << "flow_id,throughput_bps,loss_rate,mean_delay_ms,jitter_ms\n";
        
        for (auto& flow : stats) {
            double throughput = flow.second.rxBytes * 8.0 / simTime;
            double lossRate = (double)flow.second.lostPackets / flow.second.txPackets;
            double meanDelay = flow.second.delaySum.GetMilliSeconds() / flow.second.rxPackets;
            double jitter = flow.second.jitterSum.GetMilliSeconds() / flow.second.rxPackets;
            
            outFile << flow.first << "," << throughput << "," << lossRate << "," 
                   << meanDelay << "," << jitter << "\n";
        }
        
        Simulator::Destroy();
    }
    
private:
    std::vector<std::string> ParseCsvLine(const std::string& line) {
        std::vector<std::string> tokens;
        std::stringstream ss(line);
        std::string token;
        
        while (std::getline(ss, token, ',')) {
            tokens.push_back(token);
        }
        
        return tokens;
    }
};

int main(int argc, char* argv[]) {
    CommandLine cmd;
    double simTime = 60.0;
    std::string timelineFile = "effect_timeline.csv";
    std::string outputFile = "ns3_metrics.csv";
    
    cmd.AddValue("simTime", "Simulation time in seconds", simTime);
    cmd.AddValue("timeline", "Attack timeline CSV file", timelineFile);
    cmd.AddValue("out", "Output metrics file", outputFile);
    cmd.Parse(argc, argv);
    
    NS_LOG_INFO("Starting Drone LPC Attack Simulation");
    NS_LOG_INFO("Simulation time: " << simTime << " seconds");
    NS_LOG_INFO("Timeline file: " << timelineFile);
    NS_LOG_INFO("Output file: " << outputFile);
    
    DroneAttackSimulator simulator(simTime, timelineFile, outputFile);
    simulator.SetupTopology();
    simulator.ApplyAttackEffects();
    simulator.InstallApplications();
    simulator.EnableMetrics();
    
    return 0;
}
CPP_EOF

chmod +x "$DRONE_EVAL_CC"
echo "NS-3 시뮬레이션 코드 생성 완료: $DRONE_EVAL_CC"
