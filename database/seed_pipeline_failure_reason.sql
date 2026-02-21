-- 样例数据：pipeline_failure_reason（失败归因记录）
-- 关联 pipeline_history 的失败记录，通过 (case_name, failed_batch, platform) 与 (case_name, start_time, platform) 一一对应
-- 可重复执行（先清空全表再插入）
-- 执行顺序：需在 seed_pipeline_history.sql 之后执行

DELETE FROM `pipeline_failure_reason`;

INSERT INTO `pipeline_failure_reason`
  (`case_name`, `failed_batch`, `platform`, `owner`, `failed_type`, `reason`, `analyzer`)
VALUES
  -- 以下每条记录对应 seed_pipeline_history 中唯一的失败记录 (case_name, start_time, platform)
  -- 排除 test_create_order + 202601231200 + win（该组合在 ph 中有 2 条失败记录，无法唯一关联）
  ('test_pay_alipay',      '202601221500', 'ohos', '李四', '依赖服务异常',   '支付网关超时', '李四'),
  ('test_cancel_order',    '202601241800', 'mac',  '王五', '环境问题',       'mac 环境网络抖动', '王五'),
  ('test_update_avatar',   '202601281800', 'ohos', '李四', '代码缺陷',       '头像上传接口空指针', '李四'),
  ('test_add_to_cart',     '202601261400', 'win',  '赵六', '数据问题',       '购物车库存校验失败', '赵六'),
  ('test_search_empty',    '202601281800', 'ohos', '张三', '环境问题',       '搜索服务连接超时', '张三'),
  ('test_login_success',   '202601221500', 'ohos', '张三', '环境问题',       '认证服务临时不可用', '张三'),
  ('test_cancel_order',    '202601261400', 'win',  '王五', '代码缺陷',       '取消订单状态机异常', '王五'),
  ('test_update_avatar',   '202601211000', 'mac',  '李四', '依赖服务异常',   'OSS 上传失败', '李四'),
  ('test_pay_alipay',      '202601251000', 'ohos', '李四', '数据问题',       '订单金额与支付金额不一致', '李四'),
  ('test_search_keyword',  '202601201730', 'win',  '张三', '环境问题',       'ES 索引未就绪', '张三'),
  ('test_login_invalid_pwd','202601251000', 'ohos', '张三', '数据问题',       '测试账号密码被重置', '张三'),
  ('test_add_to_cart',     '202601201730', 'win',  '赵六', '代码缺陷',       '加购并发锁异常', '赵六'),
  ('test_search_empty',    '202601231200', 'win',  '张三', '其他',           '未知原因待排查', '张三'),
  ('test_change_nickname', '202601241800', 'mac',  '李四', '代码缺陷',       '昵称敏感词过滤逻辑错误', '李四'),
  ('test_create_order',    '202601281800', 'ohos', '王五', '依赖服务异常',   '库存服务调用超时', '王五'),
  ('test_cancel_order',    '202601211000', 'mac',  '王五', '环境问题',       'mac 模拟器资源不足', '王五'),
  ('test_update_avatar',   '202601251000', 'ohos', '李四', '代码缺陷',       '头像裁剪尺寸校验缺失', '李四'),
  ('test_login_invalid_pwd','202601201730', 'win',  '张三', '数据问题',       '账号被锁定', '张三'),
  ('test_search_keyword',  '202601241800', 'mac',  '张三', '环境问题',       'mac 测试环境配置错误', '张三'),
  ('test_change_nickname', '202601281800', 'ohos', '李四', '代码缺陷',       '昵称长度校验边界问题', '李四'),
  ('test_pay_alipay',      '202601231200', 'win',  '李四', '依赖服务异常',   '支付宝沙箱环境异常', '李四');
