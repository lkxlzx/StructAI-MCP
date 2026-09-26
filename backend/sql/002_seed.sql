-- =============================================================================
-- StructAI 持久层种子数据 —— SQLite 幂等 Seed
-- =============================================================================
-- 来源（唯一真源）：
--   * 权限码清单       《StructAI 架构边界与融合规范 v1.0（总纲）》§4.8.2
--   * 默认角色映射     《StructAI 架构边界与融合规范 v1.0（总纲）》§4.8.3
--   * 种子数据块       《StructAI MCP V2.1 设计框架规范》§4「19. 初始化种子数据」
--   * 表结构           同目录 001_schema.sql（49 张表）
--
-- 幂等性：全部使用 INSERT OR IGNORE（或 INSERT ... SELECT ... WHERE NOT EXISTS），
--         可重复执行，不会产生重复行，也不会覆盖已修改的运维数据。
--
-- 内容清单：
--   permissions                34 行（原 23 + system:audit + task:retry + assistant:* × 9）
--   roles                       4 行（super_admin / engineer / analyst / visitor）
--   role_permissions           34 + 21 + 6 + 4 = 65 行（按总纲 §4.8.3 展开）
--   单例配置表                  5 行（security_configs / service_configs /
--                                   backup_configs / cleanup_configs /
--                                   assistant_drawing_settings）
--   code_standards              4 行（GB50017 / GB50009 / GB50011 / GB50007）
--   assistant_commands          3 行（create_model / check_model / run_analysis）
--   assistant_templates         4 行（steel_portal_frame / concrete_frame / bridge / foundation）
--   assistant_examples          2 行（引用上述模板）
--
-- 所有 JSON 值均为合法 JSON，以单引号 SQL 字符串字面量承载，单行书写。
-- =============================================================================

PRAGMA foreign_keys = ON;

BEGIN;

-- =========================================================
-- 1. 权限码（34 条，封闭集合，逐字来自总纲 §4.8.2）
-- =========================================================
-- 编码规范 <module>:<action>（总纲 §4.8.1）。
-- ★ 标记为总纲 v1.0 新增：system:audit、task:retry、assistant:* × 9。

INSERT OR IGNORE INTO permissions(code,name,module,action)
VALUES
-- system（3）
('system:read','查看系统设置','system','read'),
('system:write','修改系统设置','system','write'),
('system:audit','查看审计日志','system','audit'),                 -- ★新增
-- model（5）
('model:read','查看模型','model','read'),
('model:create','创建模型','model','create'),
('model:update','修改模型','model','update'),
('model:delete','删除模型','model','delete'),
('model:test','测试模型','model','test'),
-- user（4）
('user:read','查看用户','user','read'),
('user:create','创建用户','user','create'),
('user:update','修改用户','user','update'),
('user:delete','删除用户','user','delete'),
-- role（2）
('role:read','查看角色','role','read'),
('role:write','修改角色权限','role','write'),
-- task（3）
('task:read','查看任务','task','read'),
('task:cancel','取消任务','task','cancel'),
('task:retry','重试任务','task','retry'),                          -- ★新增
-- tool（2）
('tool:read','查看工具','tool','read'),
('tool:execute','执行工具','tool','execute'),
-- data（6）
('data:read','查看数据','data','read'),
('data:backup','备份数据','data','backup'),
('data:restore','恢复数据','data','restore'),
('data:export','导出数据','data','export'),
('data:import','导入数据','data','import'),
('data:cleanup','清理数据','data','cleanup'),
-- assistant（9，★全部新增）
('assistant:read','查看 AI 助手','assistant','read'),
('assistant:chat','与 AI 助手对话','assistant','chat'),
('assistant:plan','生成执行计划','assistant','plan'),
('assistant:confirm','确认高风险计划','assistant','confirm'),
('assistant:execute','执行计划','assistant','execute'),
('assistant:drawing','智能识图','assistant','drawing'),
('assistant:modeling','智能建模','assistant','modeling'),
('assistant:optimize','结构优化','assistant','optimize'),
('assistant:report','生成报告','assistant','report');

-- 注：总纲 §4.8.2 的 audit 模块「复用 system:audit」，故不另立 audit:* 权限码。
-- 权限码总数校验：3 + 5 + 4 + 2 + 3 + 2 + 6 + 9 = 34。

-- =========================================================
-- 2. 默认角色（4 条）
-- =========================================================

INSERT OR IGNORE INTO roles(name,code,description,is_system)
VALUES
('超级管理员','super_admin','拥有系统全部权限',1),
('工程师','engineer','可访问 MIDAS、模型和任务功能',1),
('分析师','analyst','可访问模型分析与结果',1),
('访客','visitor','只读权限',1);

-- =========================================================
-- 3. 角色 → 权限映射（实现总纲 §4.8.3，全部幂等）
-- =========================================================

-- 3.1 super_admin = 全部（34 条）
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'super_admin';

-- 3.2 engineer = model:* + tool:* + task:* + assistant:* + system:read + data:read
--     展开为 5 + 2 + 3 + 9 + 1 + 1 = 21 条
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'engineer'
  AND (   p.code LIKE 'model:%'
       OR p.code LIKE 'tool:%'
       OR p.code LIKE 'task:%'
       OR p.code LIKE 'assistant:%'
       OR p.code IN ('system:read','data:read'));

-- 3.3 analyst = model:read + tool:read + task:read + assistant:read + assistant:chat + data:read
--     展开为 6 条
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'analyst'
  AND p.code IN (
      'model:read','tool:read','task:read',
      'assistant:read','assistant:chat','data:read'
  );

-- 3.4 visitor = model:read + tool:read + task:read + data:read
--     展开为 4 条
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'visitor'
  AND p.code IN ('model:read','tool:read','task:read','data:read');

-- 高风险权限约束（总纲 §4.8.4）——由上述映射自动满足，此处仅登记，不额外授权：
--   data:restore      → 仅 super_admin（engineer 的 data:* 不含 restore，映射中未包含）
--   system:write      → 仅 super_admin
--   user:delete       → 仅 super_admin
--   assistant:execute → engineer 及以上，且必须通过高风险确认流程（业务层强制）
--   裁决：AI 助手不得触发 data:restore（总纲 §4.8.4）。

-- =========================================================
-- 4. 单例配置表初始化（5 张表，各 1 行，主键恒为 1）
-- =========================================================
-- 这些表带 CHECK(id = 1) 约束，全局只允许一行；INSERT OR IGNORE 保证重复执行安全。

-- 4.1 security_configs：安全策略（含 rate_limit_* 三列，裁决 B-7）
INSERT OR IGNORE INTO security_configs(id) VALUES (1);

-- 4.2 service_configs：服务运行参数（log_level 归属本表，裁决 A-2）
INSERT OR IGNORE INTO service_configs(id) VALUES (1);

-- 4.3 backup_configs：备份策略（storage_path 平台自适应，裁决 C-10）
INSERT OR IGNORE INTO backup_configs(id) VALUES (1);

-- 4.4 cleanup_configs：数据清理策略
INSERT OR IGNORE INTO cleanup_configs(id) VALUES (1);

-- 4.5 assistant_drawing_settings：识图设置（补 v1.1 §76 缺表）
INSERT OR IGNORE INTO assistant_drawing_settings(id) VALUES (1);

-- =========================================================
-- 5. 规范知识库种子（4 部国标，总纲 §4.2.10 category = national）
-- =========================================================

INSERT OR IGNORE INTO code_standards(code,name,full_name,version,category,country,enabled)
VALUES
('GB50017','钢结构设计标准','钢结构设计标准','2017','national','CN',1),
('GB50009','建筑结构荷载规范','建筑结构荷载规范','2012','national','CN',1),
('GB50011','建筑抗震设计规范','建筑抗震设计规范','2010','national','CN',1),
('GB50007','建筑地基基础设计规范','建筑地基基础设计规范','2011','national','CN',1);

-- 说明：code_clauses（规范条文）与 load_parameter_library（地区荷载参数库）
-- 属业务知识内容，随规范知识库版本迭代导入，不在本基线种子中预置。
-- 注意：code_standards.category CHECK 取值域为
--   national / industry / local / enterprise / international（总纲 §4.2.10）。

-- =========================================================
-- 6. 常用工程指令（3 条，assistant_commands）
-- =========================================================
-- prompt_template 使用 {{name}} 占位符；param_schema_json 为合法 JSON Schema 片段。

INSERT OR IGNORE INTO assistant_commands
    (command_code,name,category,prompt_template,param_schema_json,sort_order,enabled)
VALUES
('create_model','快速建模','modeling',
 '按以下参数建立一个 {{structure_type}} 结构模型：{{parameters}}',
 '{"type":"object","additionalProperties":false,"properties":{"structure_type":{"type":"string"},"parameters":{"type":"object"}},"required":["structure_type","parameters"]}',
 10,1),
('check_model','模型检查','checking',
 '对当前模型执行完整性与规范检查，列出问题清单与依据条文。',
 '{"type":"object","additionalProperties":false,"properties":{"standard_codes":{"type":"array","items":{"type":"string"}}},"required":[]}',
 20,1),
('run_analysis','执行分析','analysis',
 '对当前模型执行 {{analysis_type}} 分析并给出结果摘要。',
 '{"type":"object","additionalProperties":false,"properties":{"analysis_type":{"type":"string","enum":["static","modal","buckling","response_spectrum"]}},"required":["analysis_type"]}',
 30,1);

-- =========================================================
-- 7. 工程模板（4 个，assistant_templates）
-- =========================================================
-- plan_template_json 的 step 结构遵循裁决 N-1 的可执行形式：
--   {step_no, name, tool_name, action, resource}，可直接翻译为 MCP 4 Tool 调用。

INSERT OR IGNORE INTO assistant_templates
    (template_code,name,category,discipline,description,param_schema_json,plan_template_json,is_system,sort_order,enabled)
VALUES
('steel_portal_frame','钢框架','structure','steel',
 '多层钢框架快速建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"span_x":{"type":"number"},"span_y":{"type":"number"},"bays_x":{"type":"integer"},"bays_y":{"type":"integer"},"stories":{"type":"integer"},"story_height":{"type":"number"}}}',
 '{"steps":[{"step_no":1,"name":"创建轴网","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建单元","tool_name":"midas_model","action":"create","resource":"element"}]}',
 1,10,1),
('concrete_frame','混凝土框架','structure','concrete',
 '现浇混凝土框架快速建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"bays_x":{"type":"integer"},"bays_y":{"type":"integer"},"stories":{"type":"integer"},"story_height":{"type":"number"},"concrete_grade":{"type":"string"}}}',
 '{"steps":[{"step_no":1,"name":"创建轴网","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建梁柱单元","tool_name":"midas_model","action":"create","resource":"element"}]}',
 1,20,1),
('bridge','桥梁','structure','bridge',
 '常规梁桥快速建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"span_length":{"type":"number"},"spans":{"type":"integer"},"deck_width":{"type":"number"}}}',
 '{"steps":[{"step_no":1,"name":"创建桥面轴网","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建主梁","tool_name":"midas_model","action":"create","resource":"element"}]}',
 1,30,1),
('foundation','基础','structure','geotechnical',
 '独立基础与筏板基础建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"foundation_type":{"type":"string","enum":["isolated","raft","pile"]},"plan_size_x":{"type":"number"},"plan_size_y":{"type":"number"}}}',
 '{"steps":[{"step_no":1,"name":"创建基础节点","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建边界条件","tool_name":"midas_model","action":"create","resource":"boundary"}]}',
 1,40,1);

-- =========================================================
-- 8. 示例案例（2 个，assistant_examples）
-- =========================================================
-- template_id 通过标量子查询关联 assistant_templates.template_code；
-- 若模板行缺失，子查询返回 NULL，而 template_id 可空（ON DELETE SET NULL），不会报错。

INSERT OR IGNORE INTO assistant_examples
    (example_code,name,category,description,template_id,steps_json,run_config_json,is_system,sort_order,enabled)
VALUES
('ex_steel_frame_3story','三层钢框架算例','structure',
 '三层三跨钢框架，恒载+活载+风荷载，静力分析并输出计算书',
 (SELECT id FROM assistant_templates WHERE template_code='steel_portal_frame'),
 '{"steps":[{"step_no":1,"tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"tool_name":"midas_model","action":"create","resource":"element"},{"step_no":3,"tool_name":"midas_execute","action":"analysis","resource":"model"}]}',
 '{"analysis_type":"static","generate_report":true}',
 1,10,1),
('ex_concrete_frame_2story','两层混凝土框架算例','structure',
 '两层两跨混凝土框架，静力分析与配筋结果输出',
 (SELECT id FROM assistant_templates WHERE template_code='concrete_frame'),
 '{"steps":[{"step_no":1,"tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"tool_name":"midas_model","action":"create","resource":"element"},{"step_no":3,"tool_name":"midas_execute","action":"analysis","resource":"model"}]}',
 '{"analysis_type":"static","generate_report":true}',
 1,20,1);

COMMIT;

-- =============================================================================
-- 种子数据完成。
-- 校验要点（可重复执行本文件验证幂等性）：
--   SELECT COUNT(*) FROM permissions;         -- 34
--   SELECT COUNT(*) FROM roles;               -- 4
--   SELECT COUNT(*) FROM role_permissions;    -- 65（super_admin 34 + engineer 21
--                                             --      + analyst 6 + visitor 4）
--   SELECT COUNT(*) FROM code_standards;      -- 4
--   SELECT COUNT(*) FROM assistant_commands;  -- 3
--   SELECT COUNT(*) FROM assistant_templates; -- 4
--   SELECT COUNT(*) FROM assistant_examples;  -- 2
-- =============================================================================