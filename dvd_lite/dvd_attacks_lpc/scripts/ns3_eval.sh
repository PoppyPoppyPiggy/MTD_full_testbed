#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/csma-module.h"
#include "ns3/applications-module.h"
#include "ns3/mobility-module.h"
#include "ns3/netanim-module.h"

#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <algorithm>

using namespace ns3;
NS_LOG_COMPONENT_DEFINE("DroneLpcEval");

// ---- impairment 파라미터 ----
struct Impair {
  double lossPct = 0.0;   // 0..100
  double delayMs = 0.0;
  double jitterMs = 0.0;
  double dupPct  = 0.0;   // 0..100
};

static std::string g_metricsOut;

// ---- 보조: Socket::SendTo 호출용 래퍼 ----
static void SendToHelper(Ptr<Socket> s, Ptr<Packet> p, Address to) { s->SendTo(p, 0, to); }

// ---- 임페어먼트 적용 수신기 ----
class ImpairedSink : public Application {
public:
  ImpairedSink() = default;
  void SetLocal(Address a) { m_local = a; }
  void SetImpair(Impair imp) { m_imp = imp; }

  uint64_t GetRxBytes() const { return m_rxBytes; }
  uint64_t GetDropCount() const { return m_drop; }
  uint64_t GetDupCount() const { return m_dup; }

private:
  virtual void StartApplication() {
    if (!m_socket) {
      m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
      m_socket->Bind(m_local);
      m_socket->SetRecvCallback(MakeCallback(&ImpairedSink::HandleRead, this));
      m_rng = CreateObject<UniformRandomVariable>();
    }
  }
  virtual void StopApplication() {
    if (!g_metricsOut.empty()) {
      std::ofstream ofs(g_metricsOut.c_str(), std::ios::out | std::ios::app);
      if (ofs) {
        ofs << "time_s,rx_bytes,drop_cnt,dup_cnt\n";
        ofs << Simulator::Now().GetSeconds() << ","
            << m_rxBytes << ","
            << m_drop << ","
            << m_dup  << "\n";
      }
    }
    if (m_socket) { m_socket->SetRecvCallback(MakeNullCallback<void, Ptr<Socket>>()); m_socket->Close(); }
    m_socket = nullptr;
  }

  void HandleRead(Ptr<Socket> sock) {
    Address from;
    while (Ptr<Packet> p = sock->RecvFrom(from)) {
      // drop?
      if (m_rng->GetValue(0.0, 100.0) < m_imp.lossPct) {
        m_drop++;
        continue;
      }
      // delay + jitter
      double addMs = m_imp.delayMs + m_rng->GetValue(0.0, m_imp.jitterMs);
      if (addMs > 0.0) {
        Simulator::Schedule(Seconds(addMs / 1000.0), &ImpairedSink::Deliver, this, p, from);
      } else {
        Deliver(p, from);
      }
      // duplicate?
      if (m_rng->GetValue(0.0, 100.0) < m_imp.dupPct) {
        m_dup++;
        Ptr<Packet> c = p->Copy();
        double d2 = addMs + m_rng->GetValue(0.0, 3.0);
        Simulator::Schedule(Seconds(d2 / 1000.0), &SendToHelper, sock, c, from);
      }
    }
  }

  void Deliver(Ptr<Packet> p, Address /*from*/) {
    m_rxBytes += p->GetSize(); // 단순 합계
  }

private:
  Ptr<Socket> m_socket;
  Address m_local;
  Impair m_imp;
  Ptr<UniformRandomVariable> m_rng;

  uint64_t m_rxBytes{0};
  uint64_t m_drop{0};
  uint64_t m_dup{0};
};

// ---- 타임라인 CSV 로더 ----
struct TimelineRow { double tApply=0; Impair imp; };
static std::vector<TimelineRow> LoadTimeline(const std::string& path) {
  std::vector<TimelineRow> rows;
  if (path.empty()) return rows;
  std::ifstream ifs(path.c_str());
  if (!ifs) return rows;

  std::string line; bool header=true;
  int idx_t=-1, idx_loss=-1, idx_delay=-1, idx_jitter=-1, idx_dup=-1;

  while (std::getline(ifs, line)) {
    if (line.empty()) continue;
    std::stringstream ss(line);
    std::vector<std::string> cols; std::string cell;
    while (std::getline(ss, cell, ',')) cols.push_back(cell);

    if (header) {
      header=false;
      for (size_t i=0;i<cols.size();++i) {
        std::string c=cols[i]; std::transform(c.begin(), c.end(), c.begin(), ::tolower);
        if (c=="t_apply_s"||c=="time_s"||c=="t") idx_t=i;
        else if (c=="loss_pct"||c=="loss") idx_loss=i;
        else if (c=="delay_ms"||c=="delay") idx_delay=i;
        else if (c=="jitter_ms"||c=="jitter") idx_jitter=i;
        else if (c=="dup_pct"||c=="dup") idx_dup=i;
      }
      continue;
    }

    auto getd = [&](int idx, double def)->double{
      if (idx<0 || idx>= (int)cols.size()) return def;
      try { return std::stod(cols[idx]); } catch(...) { return def; }
    };

    TimelineRow r;
    r.tApply = getd(idx_t, 0.0);
    r.imp.lossPct  = getd(idx_loss, 0.0);
    r.imp.delayMs  = getd(idx_delay, 0.0);
    r.imp.jitterMs = getd(idx_jitter,0.0);
    r.imp.dupPct   = getd(idx_dup, 0.0);
    rows.push_back(r);
  }
  std::sort(rows.begin(), rows.end(), [](auto&a, auto&b){return a.tApply<b.tApply;});
  return rows;
}

// ---- CSV 라벨 파서: "GCS,CC,FC,SIM,ATTACKER" ----
static std::vector<std::string> SplitCSV(const std::string& s) {
  std::vector<std::string> out; std::stringstream ss(s); std::string tok;
  while (std::getline(ss, tok, ',')) {
    tok.erase(std::remove_if(tok.begin(), tok.end(), ::isspace), tok.end());
    if (!tok.empty()) out.push_back(tok);
  }
  return out;
}

int main(int argc, char** argv)
{
  std::string timeline = "";
  double simTime = 35.0;
  std::string animOut = "";
  std::string pcapPrefix = "";
  g_metricsOut = "";

  // 시각화/트래픽 옵션
  std::string nodeLabels = "GCS,CC,FC,SIM,ATTACKER";  // 5개 고정
  double bgPps = 5.0;        // FC→GCS 정상 트래픽
  double atkStart = 2.0;     // 공격 시작시간
  double atkDuration = 10.0; // 공격 지속
  double atkPps = 60.0;      // 공격 트래픽 PPS
  uint16_t sinkPort = 14550; // GCS MAVLink(상징)

  CommandLine cmd(__FILE__);
  cmd.AddValue("timeline", "CSV timeline (t_apply_s,loss_pct,delay_ms,jitter_ms,dup_pct)", timeline);
  cmd.AddValue("simTime", "simulation time (seconds)", simTime);
  cmd.AddValue("animOut", "NetAnim XML output", animOut);
  cmd.AddValue("pcapPrefix", "pcap prefix", pcapPrefix);
  cmd.AddValue("metricsOut", "metrics CSV output", g_metricsOut);
  cmd.AddValue("nodeLabels", "comma labels for nodes: GCS,CC,FC,SIM,ATTACKER", nodeLabels);
  cmd.AddValue("bgPps", "background FC->GCS PPS", bgPps);
  cmd.AddValue("attackStart", "attack start time (s)", atkStart);
  cmd.AddValue("attackDuration", "attack duration (s)", atkDuration);
  cmd.AddValue("attackPps", "attacker->GCS PPS", atkPps);
  cmd.Parse(argc, argv);

  auto labels = SplitCSV(nodeLabels);
  while (labels.size()<5) labels.push_back("N"+std::to_string(labels.size()));

  // 노드: 0:GCS 1:CC 2:FC 3:SIM 4:ATTACKER  (DVD 컨테이너 4 + 공격자)
  NodeContainer n; n.Create(5);

  // 고정 위치(경고 제거용 Mobility 설치)
  MobilityHelper mob; mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  mob.Install(n);
  Ptr<ConstantPositionMobilityModel> pos0 = n.Get(0)->GetObject<ConstantPositionMobilityModel>();
  Ptr<ConstantPositionMobilityModel> pos1 = n.Get(1)->GetObject<ConstantPositionMobilityModel>();
  Ptr<ConstantPositionMobilityModel> pos2 = n.Get(2)->GetObject<ConstantPositionMobilityModel>();
  Ptr<ConstantPositionMobilityModel> pos3 = n.Get(3)->GetObject<ConstantPositionMobilityModel>();
  Ptr<ConstantPositionMobilityModel> pos4 = n.Get(4)->GetObject<ConstantPositionMobilityModel>();
  pos0->SetPosition(Vector( 20.0, 20.0, 0)); // GCS
  pos1->SetPosition(Vector( 60.0, 40.0, 0)); // CC
  pos2->SetPosition(Vector( 60.0,  0.0, 0)); // FC
  pos3->SetPosition(Vector(100.0, 20.0, 0)); // SIM
  pos4->SetPosition(Vector(  0.0, 60.0, 0)); // ATTACKER

  // LAN (Docker bridge를 CSMA로 추상화)
  CsmaHelper csma;
  csma.SetChannelAttribute("DataRate", StringValue("100Mbps"));
  csma.SetChannelAttribute("Delay", TimeValue(MicroSeconds(200)));

  NetDeviceContainer devs = csma.Install(n);

  InternetStackHelper internet; internet.Install(n);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.250.0.0", "255.255.255.0"); // 시뮬 전용 대역 (실제 DVD 대역과 분리)
  Ipv4InterfaceContainer ifs = ipv4.Assign(devs);

  // ---- GCS 수신기(임페어먼트 적용) ----
  Address gcsAny(InetSocketAddress(Ipv4Address::GetAny(), sinkPort));
  Ptr<ImpairedSink> sink = CreateObject<ImpairedSink>();
  sink->SetLocal(gcsAny);
  n.Get(0)->AddApplication(sink);
  sink->SetStartTime(Seconds(0.0));
  sink->SetStopTime(Seconds(simTime));

  // ---- FC → GCS (정상 MAVLink 모사, 낮은 PPS) ----
  {
    UdpClientHelper c(ifs.GetAddress(0), sinkPort); // target: GCS
    uint32_t maxPkts = (uint32_t)(simTime * bgPps);
    c.SetAttribute("MaxPackets", UintegerValue(maxPkts));
    c.SetAttribute("Interval", TimeValue(Seconds(1.0 / std::max(0.1, bgPps))));
    c.SetAttribute("PacketSize", UintegerValue(60));
    ApplicationContainer a = c.Install(n.Get(2)); // sender: FC
    a.Start(Seconds(0.5));
    a.Stop(Seconds(simTime));
  }

  // ---- ATTACKER → GCS (공격 트래픽) ----
  {
    UdpClientHelper c(ifs.GetAddress(0), sinkPort);
    uint32_t maxPkts = (uint32_t)(atkDuration * atkPps);
    c.SetAttribute("MaxPackets", UintegerValue(maxPkts));
    c.SetAttribute("Interval", TimeValue(Seconds(1.0 / std::max(0.1, atkPps))));
    c.SetAttribute("PacketSize", UintegerValue(60));
    ApplicationContainer a = c.Install(n.Get(4)); // sender: ATTACKER
    a.Start(Seconds(atkStart));
    a.Stop(Seconds(atkStart + atkDuration));
  }

  // ---- 타임라인 임페어먼트(GCS 수신단)에 적용 ----
  auto rows = LoadTimeline(timeline);
  for (auto &r : rows) { Simulator::Schedule(Seconds(r.tApply), &ImpairedSink::SetImpair, sink, r.imp); }

  // ---- 패킷 메타데이터/pcap/애니메이션 ----
  PacketMetadata::Enable();
  if (!pcapPrefix.empty()) { csma.EnablePcapAll(pcapPrefix, true); }

  AnimationInterface* anim = nullptr;
  if (!animOut.empty()) {
    anim = new AnimationInterface(animOut);
    anim->EnablePacketMetadata(true);
    // 라벨/색/크기
    auto setNode = [&](uint32_t i, const std::string& desc, uint8_t r, uint8_t g, uint8_t b, double sx=20.0, double sy=20.0){
      anim->UpdateNodeDescription(i, desc);
      anim->UpdateNodeColor(i, r, g, b);
      anim->UpdateNodeSize(i, sx, sy);
      // 위치는 Mobility로 이미 고정됨
    };
    setNode(0, labels[0]+" (GCS)",        46,204,113);   // green
    setNode(1, labels[1]+" (CC)",          52,152,219);  // blue
    setNode(2, labels[2]+" (FC)",         241,196, 15);  // yellow
    setNode(3, labels[3]+" (SIM)",        155, 89,182);  // purple
    setNode(4, labels[4]+" (ATTACKER)",   231, 76, 60);  // red
  }

  Simulator::Stop(Seconds(simTime));
  Simulator::Run();
  if (anim) { delete anim; }
  Simulator::Destroy();
  return 0;
}
