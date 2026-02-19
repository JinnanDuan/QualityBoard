-- 新建报告快照表 report_snapshot
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `report_snapshot` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `batch` varchar(100) NOT NULL COMMENT '轮次',
  `title` varchar(255) DEFAULT NULL COMMENT '报告标题',
  `content` text COMMENT '报告内容（JSON快照）',
  `creator` varchar(50) NOT NULL COMMENT '创建人工号',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_rs_batch` (`batch`),
  KEY `idx_rs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
