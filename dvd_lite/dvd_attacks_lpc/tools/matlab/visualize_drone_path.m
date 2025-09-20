% visualize_drone_path.m (v7.0 - Integrated Cyber/Physical Dashboard)
% bus_dvd.log(물리)와 bus.log(사이버)를 함께 시각화하는 통합 대시보드입니다.

function visualize_drone_path()
    % --- 설정 ---
    projectBasePath = '/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc';
    physLogPath = fullfile(projectBasePath, 'bus', 'bus_dvd.log'); % 물리 로그
    cyberLogPath = fullfile(projectBasePath, 'bus', 'bus.log');      % 사이버 로그

    updateInterval = 0.1;
    pathDuration_s = 5;
    earthRadius_m = 6371000;

    % --- 초기화 ---
    fprintf('>> 통합 사이버/물리 시각화 대시보드 (v7.0) 시작...\n');
    
    fig = figure('Name', '실시간 통합 시각화 대시보드', 'NumberTitle', 'off', 'Color', '#1e1e1e');
    
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
    infoText = text(ax3D, 0, 0, 0, '', 'FontSize', 10, 'Color', 'w', 'FontWeight', 'bold');
    
    % --- 이벤트 로그 패널 설정 ---
    set(axLog, 'Color', 'k', 'XColor', 'k', 'YColor', 'k', 'XTick', [], 'YTick', []);
    title(axLog, '사이버 이벤트 (bus.log)', 'Color', 'w', 'FontSize', 12);
    logTextHandles = gobjects(10, 1); % 최대 10개의 로그 라인을 표시할 핸들
    for i = 1:10
        logTextHandles(i) = text(axLog, 0.05, 1 - (i * 0.09), '', 'Color', 'w', 'FontSize', 9, 'Interpreter', 'none');
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
        
        % 사이버 이벤트 업데이트 (bus.log)
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
    file_info = dir(logPath);
    if isempty(file_info) || file_info.bytes <= lastPos, return; end
    
    fid = fopen(logPath, 'r');
    fseek(fid, lastPos, 'bof');
    
    newLines = {};
    while ~feof(fid)
        line = fgetl(fid);
        if ischar(line) && ~isempty(line), newLines{end+1} = line; end
    end
    lastPos = ftell(fid);
    fclose(fid);
    
    for i = 1:length(newLines)
        [logData, success] = parseJsonLog(newLines{i});
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
    
    armedStr = ternary(lastLogData.armed, 'ARMED', 'DISARMED');
    infoContent = sprintf('Mode: %s | Armed: %s | Battery: %d%%', lastLogData.mode, armedStr, lastLogData.battery);
    set(infoText, 'Position', [lastX, lastY, lastZ + max(5, lastZ*0.1)], 'String', infoContent);
    title(ax, sprintf('물리적 경로 | 고도: %.1f m', lastZ), 'Color', 'w');
end

function [logBuffer, lastPos] = updateCyberLog(logPath, lastPos, logBuffer)
    file_info = dir(logPath);
    if isempty(file_info) || file_info.bytes <= lastPos, return; end
    
    fid = fopen(logPath, 'r');
    fseek(fid, lastPos, 'bof');
    
    while ~feof(fid)
        line = fgetl(fid);
        if ischar(line) && ~isempty(line)
            try
                event = jsondecode(line);
                % 중요한 정보만 추출하여 한 줄로 만듦
                type = event.type;
                data_summary = jsonencode(event.data);
                if strlength(data_summary) > 70
                    data_summary = [extractBefore(data_summary, 67), '...}'];
                end
                logBuffer{end+1} = sprintf('[%s] %s', type, data_summary);
            catch
                % pass
            end
        end
    end
    lastPos = ftell(fid);
    fclose(fid);
    
    % 버퍼 크기를 10으로 유지
    if length(logBuffer) > 10
        logBuffer = logBuffer(end-9:end);
    end
end

function updateLogPanel(ax, textHandles, logBuffer)
    for i = 1:10
        if i <= length(logBuffer)
            logLine = logBuffer{i};
            color = 'w'; % 기본 흰색
            if contains(logLine, 'attack'), color = '#ff6b6b'; end % 공격은 빨간색
            if contains(logLine, 'mtd'), color = '#48dbfb'; end    % MTD는 하늘색
            if contains(logLine, 'ai_'), color = '#feca57'; end   % AI는 노란색
            set(textHandles(i), 'String', logLine, 'Color', color);
        else
            set(textHandles(i), 'String', '');
        end
    end
end

function [result, success] = parseJsonLog(jsonStr)
    result = struct(); success = false;
    try
        if ~contains(jsonStr, '"drone_state_detailed"'), return; end
        result.timestamp = str2double(extractField(jsonStr, '"ts": ([\d\.]+)'));
        result.lat = str2double(extractField(jsonStr, '"lat": ([\d\.\-]+)'));
        result.lon = str2double(extractField(jsonStr, '"lon": ([\d\.\-]+)'));
        result.alt = str2double(extractField(jsonStr, '"alt_m": ([\d\.\-]+)'));
        result.mode = extractField(jsonStr, '"mode": "([^"]+)"');
        result.armed = contains(extractField(jsonStr, '"armed": (\w+)'), 'true');
        result.battery = round(str2double(extractField(jsonStr, '"battery_pct": ([\d\.\-]+)')));
        if ~isempty(result.timestamp) && ~isempty(result.lat), success = true; end
    catch, success = false; end
end

function value = extractField(str, pattern)
    tokens = regexp(str, pattern, 'tokens');
    if ~isempty(tokens), value = tokens{1}{1}; else, value = ''; end
end

function result = ternary(condition, true_val, false_val)