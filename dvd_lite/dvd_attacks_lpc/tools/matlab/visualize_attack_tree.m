% visualize_attack_tree.m (v2.0 - Interactive JSON Selector & Full GUI)
% MITRE ATT&CK 기반의 공격 트리 JSON 파일을 사용자가 선택하여 시각화합니다.
% 이 코드는 모든 GUI 요소와 콜백 함수를 포함하는 완전한 독립 실행형 스크립트입니다.

function visualize_attack_tree()
    % --- 초기화 및 UI Figure 생성 ---
    fig = uifigure('Name', 'MITRE ATT&CK 트리 시각화', 'Position', [150, 150, 1400, 800], 'Color', '#3c3c3c');
    
    % --- 파일 선택 대화상자 ---
    jsonFolder = '/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/modules/attacks_wiki/json/';
    [file, path] = uigetfile(fullfile(jsonFolder, '*.json'), '분석할 공격 트리 JSON 파일을 선택하세요');
    
    % 사용자가 선택을 취소한 경우 종료
    if isequal(file, 0)
       disp('파일 선택이 취소되었습니다.');
       delete(fig); % Figure 창 닫기
       return;
    end
    jsonPath = fullfile(path, file);

    % --- 데이터 로드 및 파싱 ---
    try
        jsonData = jsondecode(fileread(jsonPath));
        attackTree = jsonData.attack_tree;
    catch ME
        uialert(fig, sprintf('JSON 파일 파싱 오류:\n%s', ME.message), '파일 오류', 'Icon', 'error');
        return;
    end
    
    % --- 메인 UI 그리드 레이아웃 ---
    mainGrid = uigridlayout(fig, [1, 2]);
    mainGrid.ColumnWidth = {'1x', '2x'};
    mainGrid.Padding = [10 10 10 10];
    mainGrid.ColumnSpacing = 10;

    % --- 왼쪽 패널 (트리, 공격 흐름) ---
    leftPanel = uipanel(mainGrid, 'BackgroundColor', '#2b2b2b', 'BorderType', 'none');
    leftGrid = uigridlayout(leftPanel, [2, 1]);
    leftGrid.RowHeight = {'2x', '1x'};
    leftGrid.RowSpacing = 10;
    
    % --- 오른쪽 패널 (상세 정보) ---
    rightPanel = uipanel(mainGrid, 'Title', '상세 정보', 'BackgroundColor', '#2b2b2b', 'ForegroundColor', 'white', 'FontSize', 14);

    % --- 공격 단계 트리 패널 ---
    treePanel = uipanel(leftGrid, 'Title', '공격 단계 (Attack Phases)', 'BackgroundColor', '#2b2b2b', 'ForegroundColor', 'white', 'FontSize', 12);
    
    % --- 공격 흐름 그래프 패널 ---
    flowPanel = uipanel(leftGrid, 'Title', '공격 흐름 (Attack Flow)', 'BackgroundColor', '#2b2b2b', 'ForegroundColor', 'white', 'FontSize', 12);

    % --- 트리 컨트롤 생성 ---
    rootNode = uitreenode('Text', attackTree.name, 'NodeData', attackTree);
    attackUITree = uitree(treePanel, 'Nodes', rootNode, 'SelectionChangedFcn', @nodeSelected, 'FontColor', 'white');
    
    % 트리 노드 채우기
    phases = fieldnames(attackTree.attack_phases);
    for i = 1:length(phases)
        phaseName = phases{i};
        phaseData = attackTree.attack_phases.(phaseName);
        phaseNode = uitreenode(rootNode, 'Text', sprintf('%s (%s)', phaseData.tactic_name, phaseData.tactic_id), 'NodeData', phaseData);
        
        if isfield(phaseData, 'techniques') && ~isempty(phaseData.techniques)
            for j = 1:length(phaseData.techniques)
                techData = phaseData.techniques(j);
                uitreenode(phaseNode, 'Text', sprintf('%s (%s)', techData.technique_name, techData.technique_id), 'NodeData', techData);
            end
        end
    end
    expand(attackUITree, 'all'); % 모든 노드 확장

    % --- 상세 정보 표시 영역 ---
    infoArea = uitextarea(rightPanel, 'Value', '왼쪽 트리에서 노드를 선택하여 상세 정보를 확인하세요.', 'Editable', 'off', 'FontColor', '#f0f0f0', 'BackgroundColor', '#1e1e1e', 'FontName', 'Monospaced', 'FontSize', 11);
    infoArea.Layout.Row = 1;
    infoArea.Layout.Column = 1;

    % --- 공격 흐름 그래프 생성 및 표시 ---
    ax = uiaxes(flowPanel);
    if isfield(attackTree, 'attack_flow') && ~isempty(attackTree.attack_flow)
        g = create_attack_flow_graph(attackTree);
        p = plot(ax, g, 'Layout', 'layered', 'Direction', 'right', 'NodeLabel', g.Nodes.Name, 'EdgeColor', '#ff6b6b', 'NodeColor', '#48dbfb');
        p.NodeFontColor = 'white';
        p.NodeFontSize = 10;
        p.ArrowSize = 12;
        ax.Visible = 'off';
        ax.Color = '#2b2b2b';
    else
        title(ax, '공격 흐름 정보가 없습니다.', 'Color', 'white');
    end

    % --- 콜백 함수 (노드 선택 시 호출) ---
    function nodeSelected(~, event)
        selectedNode = event.SelectedNodes;
        if isempty(selectedNode)
            return;
        end
        data = selectedNode.NodeData;
        
        fields = fieldnames(data);
        infoStr = {};
        for k = 1:length(fields)
            fieldName = strrep(fields{k}, '_', ' '); % Underscore to space
            fieldName = [upper(fieldName(1)), fieldName(2:end)]; % Capitalize first letter
            fieldValue = data.(fields{k});
            
            infoStr{end+1} = sprintf('--- %s ---\n%s', fieldName, format_value(fieldValue, '  '));
        end
        infoArea.Value = strjoin(infoStr, '\n\n');
    end

    % --- 값 포매팅 헬퍼 함수 ---
    function formattedStr = format_value(value, indent)
        if ischar(value)
            formattedStr = value;
        elseif isnumeric(value) || islogical(value)
            formattedStr = num2str(value);
        elseif isstruct(value)
            subFields = fieldnames(value);
            subStrs = {};
            for m = 1:length(subFields)
                subFieldName = strrep(subFields{m}, '_', ' ');
                subFieldName = [upper(subFieldName(1)), subFieldName(2:end)];
                subStrs{end+1} = sprintf('%s%-25s: %s', indent, subFieldName, format_value(value.(subFields{m}), [indent '    ']));
            end
            formattedStr = sprintf('\n%s', strjoin(subStrs, '\n'));
        elseif iscell(value)
            cell_content = cellfun(@(x) format_value(x, indent), value, 'UniformOutput', false);
            formattedStr = sprintf('\n%s- %s', indent, strjoin(cell_content, sprintf('\n%s- ', indent)));
        else
            formattedStr = '[Complex Data Type]';
        end
    end

    % --- 공격 흐름 그래프 생성 헬퍼 함수 ---
    function g = create_attack_flow_graph(attackTree)
        flow = attackTree.attack_flow;
        numNodes = length(flow);
        s = []; 
        t = [];
        for idx = 1:numNodes-1
            s(end+1) = idx;
            t(end+1) = idx + 1;
        end
        nodeNames = cellfun(@(x) strsplit(x, '.'), flow, 'UniformOutput', false);
        nodeLabels = cellfun(@(x) sprintf('%s\n(%s)', strrep(x{1}, '_', ' '), x{2}), nodeNames, 'UniformOutput', false);
        
        g = digraph(s, t, [], nodeLabels');
    end
end