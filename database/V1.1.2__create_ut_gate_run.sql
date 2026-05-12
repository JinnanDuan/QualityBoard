-- 新建 UT 门禁上报记录表 ut_gate_run（见 spec/15_ut_gate_jenkins_report_spec.md §5）
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `ut_gate_run` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `reported_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '门禁结束上报时间',
  `jenkins_base_url` varchar(512) DEFAULT NULL COMMENT 'Jenkins 根 URL（由 BUILD_URL 解析）',
  `job_name` varchar(256) NOT NULL COMMENT 'Job 名称',
  `build_number` int(10) unsigned NOT NULL COMMENT '构建号',
  `build_url` varchar(1024) DEFAULT NULL COMMENT '本次构建页 URL',
  `mr_url` varchar(1024) DEFAULT NULL COMMENT 'MR 页面完整 URL',
  `idempotency_key` varchar(128) NOT NULL COMMENT '幂等键（同一次 Jenkins 构建）',
  `is_intercepted` tinyint(1) NOT NULL COMMENT '是否拦截到：1=可判定且存在失败用例，0=其它',
  `ut_exit_code` int(11) DEFAULT NULL COMMENT 'cargo make test 退出码',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_idempotency` (`idempotency_key`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_mr_url_created` (`mr_url`, `created_at`),
  KEY `idx_is_intercepted_created` (`is_intercepted`, `created_at`),
  KEY `idx_job_build` (`job_name`, `build_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
