% visualize_drone_path.m (v8.0 - Next-Gen Cyber/Physical Dashboard)
% 개선된 로그 파이프라인(bus_dvd.log, bus_system_events.log)에 최적화된 통합 대시보드

function visualize_drone_path()
    % --- 설정 ---
    projectBasePath = '/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc'; % 사용자 환경에 맞게 수정
    physLogPath = fullfile(projectBasePath, 'bus', 'bus_dvd.log'); % 물리 로그 (텔레메트리)
    cyberLogPath = fullfile(projectBasePath, 'bus', 'bus_system_events.log'); % 사이버 로그 (핵심 이벤트)

    updateInterval = 0.1; % (초) 화면 갱신 주기
    pathDuration_s = 5;   % (초) 화면에 표시할 경로의 길이
    earthRadius_m = 6371000;

    % --- 초기화 ---
    fprintf('>> 통합 사이버/물리 시각화 대시보드 (v8.0) 시작...\n');
    
    fig = figure('Name', '실시간 통합 시각화 대시보드', 'NumberTitle', 'off', 'Color', '#1e1e1e', 'Position', [100, 100, 1400, 600]);
    
    % 3D 플롯과 이벤트 로그를 위한 서브플롯 생성
    ax3D = subplot(1, 2, 1, 'Parent', fig); % 왼쪽: 3D 플롯
    axLog = subplot(1, 2, 2, 'Parent', fig); % 오른쪽: 이벤트 로그

    % --- 3D 플롯 설정 ---
    set(ax3D, 'Color', '#282c34', 'GridColor', '#555', 'XColor', 'w', 'YColor', 'w', 'ZColor', 'w');
    hold(ax3D, 'on'); grid(ax3D, 'on'); axis(ax3D, 'equal'); view(ax3D, 3);
    xlabel(ax3D, 'X (m)'); ylabel(ax3D, 'Y (m)'); zlabel(ax3D, '고도 (m)');
    title(ax3D, '물리적 경로 (bus_dvd.log)', 'Color', 'w');
    
    pathPlot = plot3(ax3D, NaN, NaN, NaN, '-c', 'LineWidth', 2.5);
    currentPosPlot = plot3(ax3D, NaN, NaN, NaN, 'o', 'MarkerSize', 10, 'MarkerFaceColor', 'm', 'MarkerEdgeColor', 'w');
    infoText = text(ax3D, 0, 0, 0, '', 'FontSize', 10, 'Color', 'w', 'FontWeight', 'bold', 'VerticalAlignment', 'bottom');
    
    % --- 이벤트 로그 패널 설정 ---
    set(axLog, 'Color', 'k', 'XColor', 'k', 'YColor', 'k', 'XTick', [], 'YTick', []);
    title(axLog, '사이버 이벤트 (bus_system_events.log)', 'Color', 'w', 'FontSize', 12);
    logTextHandles = gobjects(10, 1); % 최대 10개의 로그 라인을 표시할 핸들
    for i = 1:10
        logTextHandles(i) = text(axLog, 0.05, 1 - (i * 0.09), '', 'Color', 'w', 'FontSize', 9, 'Interpreter', 'none', 'FontName', 'Monospaced');
    end
    
    % --- 데이터 변수 ---
    pathData = []; origin = []; lastPhysPos = 0;
    cyberLogBuffer = {}; lastCyberPos = 0;

    % --- 메인 루프 ---
    while ishandle(fig)
        % 물리적 경로 업데이트 (bus_dvd.log)
        [pathData, origin, lastPhysPos, lastLogData] = updatePhysicalPlot(physLogPath, lastPhysPos, pathData, origin, earthRadius_m, pathDuration_s);
        if ~isempty(lastLogData)
            update3DGraphics(ax3D, pathPlot, currentPosPlot, infoText, pathData, lastLogData);
        end
        
        % 사이버 이벤트 업데이트 (bus_system_events.log)
        [cyberLogBuffer, lastCyberPos] = updateCyberLog(cyberLogPath, lastCyberPos, cyberLogBuffer);
        updateLogPanel(axLog, logTextHandles, cyberLogBuffer);

        pause(updateInterval);
        drawnow limitrate;
    end
    fprintf('>> 시각화 스크립트를 종료합니다.\n');
end

% --- 헬퍼 함수들 ---
function [pathData, origin, lastPos, lastLogData] = updatePhysicalPlot(logPath, lastPos, pathData, origin, R, duration)
    lastLogData = [];
    newLines = readNewLines(logPath, lastPos);
    if isempty(newLines), return; end
    lastPos = newLines.newPos;
    
    for i = 1:length(newLines.lines)
        [logData, success] = parsePhysicalLog(newLines.lines{i});
        if ~success, continue; end
        lastLogData = logData; % 마지막 유효 데이터 저장
        
        if isempty(origin)
            origin.lat = logData.lat; origin.lon = logData.lon; origin.alt = logData.alt;
        end
        
        x = R * (logData.lon - origin.lon) * cosd(origin.lat);
        y = R * (logData.lat - origin.lat);
        z = logData.alt - origin.alt;
        
        pathData(end+1, :) = [logData.timestamp, x, y, z];
    end
    
    if ~isempty(pathData)
        latestTimestamp = pathData(end, 1);
        pathData(pathData(:, 1) < (latestTimestamp - duration), :) = [];
    end
end

function update3DGraphics(ax, pathPlot, currentPosPlot, infoText, pathData, lastLogData)
    if isempty(pathData), return; end
    lastX = pathData(end, 2); lastY = pathData(end, 3); lastZ = pathData(end, 4);
    
    set(pathPlot, 'XData', pathData(:, 2), 'YData', pathData(:, 3), 'ZData', pathData(:, 4));
    set(currentPosPlot, 'XData', lastX, 'YData', lastY, 'ZData', lastZ);
    
    armedStr = 'DISARMED';
    if lastLogData.armed, armedStr = 'ARMED'; end
    
    infoContent = sprintf('Mode: %s | %s | Battery: %d%%', lastLogData.mode, armedStr, lastLogData.battery);
    set(infoText, 'Position', [lastX, lastY, lastZ + max(5, lastZ*0.1)], 'String', infoContent);
    title(ax, sprintf('물리적 경로 | 고도: %.1f m', lastZ), 'Color', 'w');
end

function [logBuffer, lastPos] = updateCyberLog(logPath, lastPos, logBuffer)
    newLines = readNewLines(logPath, lastPos);
    if isempty(newLines), return; end
    lastPos = newLines.newPos;
    
    for i = 1:length(newLines.lines)
        try
            event = jsondecode(newLines.lines{i});
            summary = formatCyberEvent(event);
            logBuffer{end+1} = summary;
        catch ME
            % fprintf('Cyber log JSON parsing error: %s\n', ME.message);
        end
    end
    
    % 버퍼 크기를 10으로 유지
    if length(logBuffer) > 10
        logBuffer = logBuffer(end-9:end);
    end
end

function summary = formatCyberEvent(event)
    % 주요 이벤트를 식별하여 가독성 좋은 포맷으로 변경
    type = event.type;
    data = event.data;
    summary = sprintf('[%s] %s', type, jsonencode(data)); % 기본 포맷

    if strcmp(type, 'attack_started') && isfield(data, 'attack')
        summary = sprintf('ATTACK STARTED: %s on %s', data.attack, data.target);
    elseif strcmp(type, 'attack_finished') && isfield(data, 'attack')
        summary = sprintf('ATTACK FINISHED: %s (code: %d)', data.attack, data.return_code);
    elseif strcmp(type, 'mtd_triggered') && isfield(data, 'strategy')
        summary = sprintf('MTD TRIGGERED: %s -> %s', data.strategy, data.details);
    elseif strcmp(type, 'ai_cti_classification') && isfield(data, 'predicted_category')
        summary = sprintf('AI DETECTION: %s (%s)', data.predicted_category, data.confidence);
    elseif strcmp(type, 'recon_found_target') && isfield(data, 'target')
        summary = sprintf('RECON: Attacker found new target at %s', data.target);
    end
end

function updateLogPanel(ax, textHandles, logBuffer)
    for i = 1:10
        if i <= length(logBuffer)
            logLine = logBuffer{end-i+1}; % 최신 로그가 위로 오도록 수정
            color = 'w'; % 기본 흰색
            if contains(logLine, 'ATTACK', 'IgnoreCase', true), color = '#ff6b6b'; end % 공격은 빨간색
            if contains(logLine, 'MTD', 'IgnoreCase', true), color = '#48dbfb'; end    % MTD는 하늘색
            if contains(logLine, 'AI', 'IgnoreCase', true), color = '#feca57'; end     % AI는 노란색
            if contains(logLine, 'RECON', 'IgnoreCase', true), color = '#ff9f43'; end % 정찰은 주황색
            set(textHandles(i), 'String', ['> ' logLine], 'Color', color);
        else
            set(textHandles(i), 'String', '');
        end
    end
end

function [result, success] = parsePhysicalLog(jsonStr)
    result = struct(); success = false;
    try
        logData = jsondecode(jsonStr);
        if ~strcmp(logData.type, 'drone_state_detailed'), return; end
        data = logData.data;
        
        % 필수 필드 존재 여부 확인
        required_fields = {'lat', 'lon', 'alt_m', 'mode', 'armed', 'battery_pct'};
        if ~all(isfield(data, required_fields)), return; end

        result.timestamp = logData.ts;
        result.lat = data.lat;
        result.lon = data.lon;
        result.alt = data.alt_m;
        result.mode = data.mode;
        result.armed = data.armed;
        result.battery = round(data.battery_pct);
        success = true;
    catch
        success = false;
    end
end

function newLines = readNewLines(logPath, lastPos)
    % 파일에서 마지막으로 읽은 위치 이후의 새로운 라인을 읽어옴
    newLines = [];
    file_info = dir(logPath);
    if isempty(file_info) || file_info.bytes <= lastPos, return; end
    
    try
        fid = fopen(logPath, 'r');
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
        % 파일 접근 오류 발생 시 무시
    end
end