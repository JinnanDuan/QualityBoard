-- 样例数据：pipeline_history（20 条）
-- 用于端到端验证，可重复执行（先清理再插入）

DELETE FROM `pipeline_history` WHERE `start_time` IN ('2026-02-19_10:00:00', '2026-02-19_14:00:00');

INSERT INTO `pipeline_history`
  (`start_time`, `subtask`, `module`, `case_name`, `case_result`, `log_url`, `screenshot_url`, `pipeline_url`, `reports_url`, `case_level`, `main_module`, `owner`, `platform`, `code_branch`, `analyzed`)
VALUES
  ('2026-02-19_10:00:00', 'group-A', 'login',    'test_login_success',         'passed', 'http://log/1',  'http://img/1',  'http://jenkins/1',  'http://report/1',  'P0', 'auth',     '张三', 'Android', 'main',    0),
  ('2026-02-19_10:00:00', 'group-A', 'login',    'test_login_invalid_pwd',     'passed', 'http://log/2',  'http://img/2',  'http://jenkins/1',  'http://report/1',  'P1', 'auth',     '张三', 'Android', 'main',    0),
  ('2026-02-19_10:00:00', 'group-A', 'payment',  'test_pay_alipay',            'failed', 'http://log/3',  'http://img/3',  'http://jenkins/1',  'http://report/1',  'P0', 'payment',  '李四', 'Android', 'main',    1),
  ('2026-02-19_10:00:00', 'group-B', 'order',    'test_create_order',          'passed', 'http://log/4',  'http://img/4',  'http://jenkins/2',  'http://report/2',  'P0', 'order',    '王五', 'iOS',     'main',    0),
  ('2026-02-19_10:00:00', 'group-B', 'order',    'test_cancel_order',          'failed', 'http://log/5',  'http://img/5',  'http://jenkins/2',  'http://report/2',  'P1', 'order',    '王五', 'iOS',     'main',    0),
  ('2026-02-19_10:00:00', 'group-B', 'cart',     'test_add_to_cart',           'passed', 'http://log/6',  'http://img/6',  'http://jenkins/2',  'http://report/2',  'P2', 'cart',     '赵六', 'iOS',     'main',    0),
  ('2026-02-19_10:00:00', 'group-C', 'search',   'test_search_keyword',        'passed', 'http://log/7',  'http://img/7',  'http://jenkins/3',  'http://report/3',  'P1', 'search',   '张三', 'Web',     'develop', 0),
  ('2026-02-19_10:00:00', 'group-C', 'search',   'test_search_empty',          'passed', 'http://log/8',  'http://img/8',  'http://jenkins/3',  'http://report/3',  'P2', 'search',   '张三', 'Web',     'develop', 0),
  ('2026-02-19_10:00:00', 'group-C', 'profile',  'test_update_avatar',         'failed', 'http://log/9',  'http://img/9',  'http://jenkins/3',  'http://report/3',  'P1', 'profile',  '李四', 'Web',     'develop', 1),
  ('2026-02-19_10:00:00', 'group-C', 'profile',  'test_change_nickname',       'passed', 'http://log/10', 'http://img/10', 'http://jenkins/3',  'http://report/3',  'P2', 'profile',  '李四', 'Web',     'develop', 0),
  ('2026-02-19_14:00:00', 'group-A', 'login',    'test_login_success',         'passed', 'http://log/11', 'http://img/11', 'http://jenkins/4',  'http://report/4',  'P0', 'auth',     '张三', 'Android', 'main',    0),
  ('2026-02-19_14:00:00', 'group-A', 'login',    'test_login_invalid_pwd',     'passed', 'http://log/12', 'http://img/12', 'http://jenkins/4',  'http://report/4',  'P1', 'auth',     '张三', 'Android', 'main',    0),
  ('2026-02-19_14:00:00', 'group-A', 'payment',  'test_pay_alipay',            'passed', 'http://log/13', 'http://img/13', 'http://jenkins/4',  'http://report/4',  'P0', 'payment',  '李四', 'Android', 'main',    0),
  ('2026-02-19_14:00:00', 'group-B', 'order',    'test_create_order',          'passed', 'http://log/14', 'http://img/14', 'http://jenkins/5',  'http://report/5',  'P0', 'order',    '王五', 'iOS',     'main',    0),
  ('2026-02-19_14:00:00', 'group-B', 'order',    'test_cancel_order',          'passed', 'http://log/15', 'http://img/15', 'http://jenkins/5',  'http://report/5',  'P1', 'order',    '王五', 'iOS',     'main',    0),
  ('2026-02-19_14:00:00', 'group-B', 'cart',     'test_add_to_cart',           'failed', 'http://log/16', 'http://img/16', 'http://jenkins/5',  'http://report/5',  'P2', 'cart',     '赵六', 'iOS',     'main',    0),
  ('2026-02-19_14:00:00', 'group-C', 'search',   'test_search_keyword',        'passed', 'http://log/17', 'http://img/17', 'http://jenkins/6',  'http://report/6',  'P1', 'search',   '张三', 'Web',     'develop', 0),
  ('2026-02-19_14:00:00', 'group-C', 'search',   'test_search_empty',          'failed', 'http://log/18', 'http://img/18', 'http://jenkins/6',  'http://report/6',  'P2', 'search',   '张三', 'Web',     'develop', 0),
  ('2026-02-19_14:00:00', 'group-C', 'profile',  'test_update_avatar',         'passed', 'http://log/19', 'http://img/19', 'http://jenkins/6',  'http://report/6',  'P1', 'profile',  '李四', 'Web',     'develop', 0),
  ('2026-02-19_14:00:00', 'group-C', 'profile',  'test_change_nickname',       'passed', 'http://log/20', 'http://img/20', 'http://jenkins/6',  'http://report/6',  'P2', 'profile',  '李四', 'Web',     'develop', 0);
