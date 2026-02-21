-- 样例数据：case_failed_type（失败类型，供标注弹窗使用）
-- 可重复执行（先清空再插入）
-- 执行顺序：需在 seed_ums_email.sql 之后执行（owner 可引用 employee_id）

DELETE FROM `case_failed_type`;

INSERT INTO `case_failed_type` (`failed_reason_type`, `owner`, `creator`, `updater`)
VALUES
  ('bug', 'W00001', 'system', 'system'),
  ('环境问题', 'W00002', 'system', 'system'),
  ('数据问题', 'W00002', 'system', 'system'),
  ('依赖服务异常', 'W00003', 'system', 'system'),
  ('代码缺陷', 'W00001', 'system', 'system'),
  ('其他', 'W00002', 'system', 'system');
