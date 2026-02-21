-- 样例数据：ums_module_owner（模块负责人，供标注弹窗 bug 类型时使用）
-- 可重复执行（INSERT IGNORE 跳过已存在的记录）
-- 执行顺序：需在 seed_ums_email.sql 之后执行（owner 外键引用 employee_id）

INSERT IGNORE INTO `ums_module_owner` (`module`, `owner`, `for_reference`)
VALUES
  ('auth', 'W00001', '张三丰'),
  ('payment', 'W00002', '李四'),
  ('order', 'W00003', '王五'),
  ('cart', 'W00002', '李四'),
  ('search', 'W00001', '张三丰'),
  ('profile', 'W00002', '李四');
