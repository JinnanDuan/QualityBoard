-- 样例数据：ums_email（登录认证 E2E 验证用）
-- 可重复执行（INSERT IGNORE 跳过已存在的记录）

INSERT IGNORE INTO `ums_email` (`employee_id`, `name`, `email`, `domain_account`)
VALUES
  ('W00001', '张三丰', 'zhangsan@example.com', 'zhangsan'),
  ('W00002', '李四', 'lisi@example.com',     'lisi'),
  ('W00003', '王五', 'wangwu@example.com',   'wangwu'),
  ('W00004', '司马相如', 'sima@example.com', 'sima');
