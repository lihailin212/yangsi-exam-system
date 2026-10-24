-- ============================================================
-- 杨思学考试系统 - Supabase PostgreSQL 迁移脚本
-- 运行方式：在 Supabase SQL Editor 中执行此脚本
-- ============================================================

-- ===================== SCHEMA =====================
DROP TABLE IF EXISTS exam_distributions CASCADE;
DROP TABLE IF EXISTS exam_records CASCADE;
DROP TABLE IF EXISTS exam_question CASCADE;
DROP TABLE IF EXISTS exams CASCADE;
DROP TABLE IF EXISTS questions CASCADE;
DROP TABLE IF EXISTS users CASCADE;

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  employee_id VARCHAR UNIQUE NOT NULL,
  name VARCHAR NOT NULL DEFAULT '',
  password_hash VARCHAR NOT NULL DEFAULT '',
  dept VARCHAR NOT NULL DEFAULT '',
  role VARCHAR NOT NULL DEFAULT '',
  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE questions (
  id SERIAL PRIMARY KEY,
  type VARCHAR NOT NULL DEFAULT 'single',
  content TEXT NOT NULL DEFAULT '',
  options TEXT NOT NULL DEFAULT '[]',
  answer VARCHAR NOT NULL DEFAULT '',
  analysis TEXT NOT NULL DEFAULT '',
  category VARCHAR NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE exams (
  id SERIAL PRIMARY KEY,
  title VARCHAR NOT NULL DEFAULT '',
  duration INTEGER NOT NULL DEFAULT 90,
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  pass_score INTEGER NOT NULL DEFAULT 60,
  single_score INTEGER NOT NULL DEFAULT 10,
  multiple_score INTEGER NOT NULL DEFAULT 20,
  judgment_score INTEGER NOT NULL DEFAULT 5,
  retake_limit INTEGER NOT NULL DEFAULT 0,
  total_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  created_by INTEGER,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE exam_question (
  exam_id INTEGER NOT NULL,
  question_id INTEGER NOT NULL,
  PRIMARY KEY (exam_id, question_id)
);

CREATE TABLE exam_records (
  id SERIAL PRIMARY KEY,
  exam_id INTEGER,
  user_id INTEGER NOT NULL,
  answers TEXT NOT NULL DEFAULT '{}',
  score DOUBLE PRECISION NOT NULL DEFAULT 0,
  total_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  submitted_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE exam_distributions (
  id SERIAL PRIMARY KEY,
  exam_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  invite_code VARCHAR UNIQUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ===================== INDEXES =====================
CREATE INDEX idx_exam_records_exam_id ON exam_records(exam_id);
CREATE INDEX idx_exam_records_user_id ON exam_records(user_id);
CREATE INDEX idx_exam_distributions_exam_id ON exam_distributions(exam_id);
CREATE INDEX idx_exam_distributions_user_id ON exam_distributions(user_id);
CREATE INDEX idx_exam_distributions_invite_code ON exam_distributions(invite_code);
CREATE INDEX idx_exams_created_by ON exams(created_by);

-- ===================== DATA =====================
-- users (密码均为 admin123)
INSERT INTO users (employee_id, name, password_hash, dept, role, is_admin, is_active, created_at) VALUES
('admin', '管理员', '$2b$12$6Bi32rPXguvaGV11mEi3Y.iv5e01Fq1xUtpqb2aWNjzPm7oM1Fvu6', '管理部', '系统管理员', TRUE, TRUE, '2026-04-12 14:28:20.668486'),
('5303', '唐金玉', '$2b$12$scqFgTPPsWmw2tkBOMNSheWjZ7pEJ.l8nQHMKmw.dmPxY1rGHrgj2', '检验科', '副主任检验师', FALSE, TRUE, '2026-04-13 10:40:30.018947'),
('5304', '丁延超', '$2b$12$n9t3k9xStxHSvqJhkbMQvuxUMs2cQ584rUIGNqxHP9qSjfHlNbjgi', '检验科', '主管检验师', FALSE, TRUE, '2026-04-13 10:41:03.771974'),
('5306', '徐寅', '$2b$12$CxDLke3NHfZt/mwgfr83w.LCCLxP1QfvDns2NVVn0mzTMyhyqXqA2', '检验科', '主管检验师', FALSE, TRUE, '2026-04-13 10:41:41.359289'),
('5308', '李海林', '$2b$12$LZoaiIUQHNREvq/qpefewOdo0nnBWfOZXH3NboMNg7O8qq4EumzGC', '检验科', '副主任检验师', TRUE, TRUE, '2026-04-13 10:42:28.492712'),
('5311', '范宜忠', '$2b$12$O3NrL86WDgbROsQ2OuN2IOyQmtpbKiXhgtYG40gy5kIdIdEYsoRDe', '检验科', '主管检验师', FALSE, TRUE, '2026-04-15 14:54:06.510445');

-- questions
INSERT INTO questions (type, content, options, answer, analysis, category, created_at) VALUES
('single', '<p>[SYSTEM_CATEGORY]解剖学</p>', '{"A": "系统分类"}', 'A', '系统分类占位题目，不在题目列表中显示', '解剖学', '2026-04-12 14:35:16.965543'),
('single', '<p>请选择图中箭头所指细胞名称</p><img src="/uploads/images/20260412_1c9d88384b5d491292dd9261ecdf116b.jpg" alt="image" style="max-width: 50%;" />', '{"A": "正常红细胞", "B": "靶形红细胞", "C": "椭圆形红细胞", "D": "嗜多色性红细胞"}', 'C', '', '形态学/血细胞形态学', '2026-04-12 14:37:52.286526'),
('single', '<p>请选择图中箭头所指细胞名称：</p><img src="/uploads/images/20260412_7b1ed64c728e4c85992d0d997c480b6e.jpg" alt="image" style="max-width: 50%;" />', '{"A": "粘液丝", "B": "植物残渣", "C": "真菌孢子", "D": "真菌菌丝"}', 'D', '', '形态学/寄生虫形态学', '2026-04-12 14:37:52.286531'),
('single', '<p>请选择图中箭头所指细胞名称</p><img src="/uploads/images/20260412_b0004a8f262b438dab24f6b2b153096f.jpg" alt="image" style="max-width: 50%;" />', '{"A": "花粉", "B": "绦虫卵", "C": "鞭虫卵", "D": "血吸虫卵"}', 'C', '', '形态学/寄生虫形态学', '2026-04-12 14:37:52.286535'),
('single', '<p>请选择图中箭头所指细胞名称：</p><img src="/uploads/images/20260412_a71494be904147d9ba3503c6f42e4810.png" alt="image" style="max-width: 50%;" />', '{"A": "单核细胞", "B": "中性中幼粒细胞", "C": "原始细胞", "D": "异常早幼粒细胞"}', 'C', '', '形态学/血细胞形态学', '2026-04-12 14:37:52.286539'),
('single', '<p>请选择图中箭头所指细胞名称：</p><img src="/uploads/images/20260411_fbaa757fc492434f9c5799841301d8a9.jpg" alt="image" style="max-width: 50%;" />', '{"A": "靶形红细胞", "B": "正常红细胞", "C": "裂片红细胞", "D": "岛形红细胞"}', 'A', '', '形态学/血细胞形态学', '2026-04-12 14:37:52.286547'),
('single', '<p>请选择图中箭头所指细胞名称：</p><img src="/uploads/images/20260411_2c0d7af33adb45e499ee8b6a1bf8ee8b.jpg" alt="image" style="max-width: 50%;" />', '{"A": "反应性淋巴细胞", "B": "淋巴细胞", "C": "原始细胞", "D": "浆细胞"}', 'D', '', '形态学/血细胞形态学', '2026-04-12 14:37:52.286550'),
('single', '<p>请选择图中箭头所指细胞名称：</p><img src="/uploads/images/20260411_2c0d7af33adb45e499ee8b6a1bf8ee8b.jpg" alt="image" style="max-width: 50%;" />', '{"A": "反应性淋巴细胞", "B": "淋巴细胞", "C": "原始细胞", "D": "浆细胞"}', 'D', '', '形态学/血细胞形态学', '2026-04-12 14:37:52.286553'),
('single', '<p>请选择图中箭头所指细胞名称</p><img src="/uploads/images/20260411_88ff16ea18474262b4d896b7dea89c6f.jpg" alt="image" style="max-width: 50%;" />', '{"A": "杂质", "B": "淋巴细胞", "C": "涂抹细胞", "D": "血小板"}', 'C', '', '形态学/血细胞形态学', '2026-04-12 14:37:52.286558'),
('single', '<p>请选择图中细胞名称：</p><img src="/uploads/images/20260411_a7a11eac6ab64dc18bf5ec3da88ffb36.jpg" alt="image" style="max-width: 50%;" />', '{"A": "钩虫卵", "B": "血吸虫卵", "C": "肝吸虫卵", "D": "蛔虫卵"}', 'B', '', '形态学/寄生虫形态学', '2026-04-12 14:37:52.286561'),
('single', '人体最大的器官是什么？', '{"A": "皮肤", "B": "肝脏", "C": "心脏", "D": "肺"}', 'A', '', '解剖学', '2026-04-12 14:37:52.286563'),
('single', '<p>[SYSTEM_CATEGORY]尿沉渣形态学</p>', '{"A": "系统分类"}', 'A', '系统分类占位题目，不在题目列表中显示', '形态学/尿沉渣形态学', '2026-04-12 14:49:48.697868'),
('single', '<p>[SYSTEM_CATEGORY]其他体液形态学</p>', '{"A": "系统分类"}', 'A', '系统分类占位题目，不在题目列表中显示', '形态学/其他体液形态学', '2026-04-12 14:49:58.295216'),
('single', '<p>[SYSTEM_CATEGORY]POCT</p>', '{"A": "系统分类"}', 'A', '系统分类占位题目，不在题目列表中显示', 'POCT', '2026-04-12 14:50:08.890933'),
('single', '<p><span style="color: rgb(25, 27, 31); background-color: rgb(255, 255, 255);"><strong>双糖铁培养基属于()</strong></span></p>', '{"A":"基础培养基","B":"鉴别培养基","C":"营养培养基","D":"选择培养基"}', 'B', '鉴别培养基是指利用细菌分解糖类和蛋白质的能力及其代谢产物的不同，在培养基中加入特定的作用底物和指示剂，观察细菌生长过程中分解底物所释放的不同产物，通过指示剂的反应不同来鉴别细菌。双糖铁培养基含有乳糖和葡萄糖，根据不同菌发酵两种糖类的不同结果对所接种的细菌进行鉴别，属于鉴别培养基', '微生物', '2026-04-13 11:15:52.048031'),
('judgment', '<p><span style="color: rgb(25, 27, 31); background-color: rgb(255, 255, 255);"><strong>病毒培养应选用</strong></span><span style="color: rgb(25, 27, 31); background-color: rgb(255, 255, 255);">活细胞培养基</span></p>', '{"A":"","B":"","C":"","D":""}', '正确', '病毒缺乏完整的酶系统，无细胞器，不能独立进行代谢活动，故不能在无生命的培养基内生长繁殖，而只能寄生于活细胞内，依靠宿主细胞提供原料和酶系统进行病毒增殖。病毒的分离可用细胞培养或动物接种和传代。', '微生物', '2026-04-13 11:17:33.977343'),
('single', '<p><span style="color: rgb(25, 27, 31); background-color: rgb(255, 255, 255);"><strong>检测HBV感染最直接敏感的指标是血液中的</strong></span></p>', '{"A":"HBsAg","B":"HBeAg","C":"HBcAg","D":"HBV-DNA"}', 'D', '应用核酸杂交技术、常规PCR技术或荧光定量技术可以直接检测血清中的HBV-DNA，这些方法特异性强，敏感性高，可测出极微量的病毒。检出HBV-DNA是病毒存在和复制的最可靠的指标。', '免疫学', '2026-04-13 11:19:20.621721'),
('single', '<p><span style="color: rgb(25, 27, 31); background-color: rgb(255, 255, 255);"><strong>符合光的吸收定律的分光光度计的条件是()</strong></span></p>', '{"A":"各种浓度的溶液","B":"10%浓度的溶液","C":"较稀的溶液","D":"5%~10%浓度的溶液"}', 'C', '在分光光度分析中，比尔定律是一个有限的定律，其成立条件是待测物为均一的稀溶液、气体等，无溶质、溶剂及悬浊物引起的散射。', '生物化学', '2026-04-13 11:21:37.188727'),
('judgment', '<p>抗凝管中溶血实验检测的是全血。</p>', '{"A":"","B":"","C":"","D":""}', '正确', '', '血液学', '2026-04-13 11:25:54.321840'),
('judgment', '<p>空腹血糖正常参考值范围为5-7mmol/L</p>', '{"A":"","B":"","C":"","D":""}', '错误', '', '生物化学', '2026-04-13 11:27:56.324737'),
('multiple', '<p>关于<span style="color: rgb(0, 0, 0); background-color: rgba(0, 0, 0, 0); font-size: 16px;"><strong>红细胞沉降率（ESR）病理性增快</strong></span>的原因，下列正确的有（）</p>', '{"A":"急性细菌性感染","B":"严重组织损伤及大量血细胞破坏","C":"恶性肿瘤","D":"高胆固醇血症","E":"妊娠 3 个月以上"}', 'A,B,C,D', '', '血液学', '2026-04-14 01:56:13.361836'),
('multiple', '<p>关于<span style="color: rgb(0, 0, 0); background-color: rgba(0, 0, 0, 0); font-size: 16px;"><strong>补体活化经典途径</strong></span>的特点，下列说法正确的有（）</p>', '{"A":"激活物主要是抗原 - 抗体复合物（IgG、IgM 类）","B":"识别单位为 C1q、C1r、C1s","C":"激活顺序为 C1→C4→C2→C3→C5～C9","D":"在感染早期即可快速、广泛激活发挥作用","E":"C3 转化酶为 C4b2a"}', 'A,B,C,E', 'A 正确：经典途径主要由IgG/IgM 类免疫复合物激活。\nB 正确：C1q、C1r、C1s 构成起始识别单位。\nC 正确：经典途径激活顺序为 C1→C4→C2→C3→C5～C9。\nD 错误：感染早期快速激活的是旁路途径和 MBL 途径，经典途径启动较晚。\nE 正确：经典途径 C3 转化酶为C4b2a。', '免疫学', '2026-04-14 02:27:05.230548'),
('single', '<p>请选择图中箭头所指细胞名称：<img src="/uploads/images/20260414_1ab5b22bf6e842e9aed2f8db393a162f.jpg" alt="单核细胞.jpg" data-href="/uploads/images/20260414_1ab5b22bf6e842e9aed2f8db393a162f.jpg" style=""/></p>', '{"A":"单核细胞","B":"淋巴细胞","C":"中性中幼粒细胞","D":"反应性淋巴细胞"}', 'A', '', '形态学/血细胞形态学', '2026-04-14 02:38:34.280865'),
('single', '<p>请选择图中箭头所指细胞内成分名称：<img src="/uploads/images/20260414_839e9df2ef584065993ef34282f7ffb2.png" alt="杜勒小体.png" data-href="/uploads/images/20260414_839e9df2ef584065993ef34282f7ffb2.png" style=""/></p>', '{"A":"杜勒小体","B":"绿色小体","C":"空泡","D":"杂质"}', 'A', '', '形态学/血细胞形态学', '2026-04-14 02:42:22.581258'),
('single', '<p>下图是什么细胞？<img src="/uploads/images/20260414_180aac53852d4588a90aba74f2facaff.jpg" alt="多发性骨髓瘤.jpg" data-href="/uploads/images/20260414_180aac53852d4588a90aba74f2facaff.jpg" style=""/></p>', '{"A":"淋巴瘤细胞","B":"骨髓瘤细胞","C":"单核细胞","D":"反应性淋巴细胞"}', 'B', '', '形态学/血细胞形态学', '2026-04-14 02:44:46.837822'),
('single', '<p>[SYSTEM_CATEGORY]形态学</p>', '{"A": "系统分类"}', 'A', '系统分类占位题目，不在题目列表中显示', '形态学/形态学', '2026-04-14 02:53:50.805008'),
('single', '<p>请选择下图中细胞名称<img src="/uploads/images/20260414_33a7af07c24e4c138ae90c0ec8ef8a59.jpg" alt="浆细胞.jpg" data-href="/uploads/images/20260414_33a7af07c24e4c138ae90c0ec8ef8a59.jpg" style=""/></p>', '{"A":"淋巴细胞","B":"单核细胞","C":"原始细胞","D":"浆细胞"}', 'D', '', '形态学/血细胞形态学', '2026-04-14 02:56:13.458691'),
('single', '<p>请选择下图箭头所指细胞名称：<img src="/uploads/images/20260414_917396dfa1fe447f95993f8d6b262771.png" alt="宽幅管型.png" data-href="/uploads/images/20260414_917396dfa1fe447f95993f8d6b262771.png" style=""/></p>', '{"A":"植物纤维","B":"粘液丝","C":"宽幅管型","D":"颗粒管型"}', 'C', '', '形态学/尿沉渣形态学', '2026-04-14 02:58:40.486293'),
('single', '<p>请选择下图箭头所指细胞名称<img src="/uploads/images/20260414_3c57ed038a0843a49ba498046e3c62e4.jpg" alt="蓝氏贾第鞭毛虫包囊.jpg" data-href="/uploads/images/20260414_3c57ed038a0843a49ba498046e3c62e4.jpg" style=""/></p>', '{"A":"蛲虫卵","B":"蓝氏贾第鞭毛虫包囊","C":"鞭虫卵","D":"阿米巴包囊"}', 'B', '', '形态学/寄生虫形态学', '2026-04-14 03:00:37.278665'),
('single', '<p>请选择下图细胞名称<img src="/uploads/images/20260414_e682966b9f054fad9bde5c3a6e319dfa.jpg" alt="淋巴细胞.jpg" data-href="/uploads/images/20260414_e682966b9f054fad9bde5c3a6e319dfa.jpg" style=""/></p>', '{"A":"淋巴细胞","B":"单核细胞","C":"小巨核细胞","D":"浆细胞"}', 'A', '', '形态学/血细胞形态学', '2026-04-14 03:01:45.601610'),
('single', '<p>请选择下图细胞名称<img src="/uploads/images/20260414_5062a53cdaec48ca8f231dee3d38c4e6.jpg" alt="尿酸结晶.jpg" data-href="/uploads/images/20260414_5062a53cdaec48ca8f231dee3d38c4e6.jpg" style=""/></p>', '{"A":"胆固醇结晶","B":"尿酸结晶","C":"胱氨酸结晶","D":"草酸钙结晶"}', 'B', '', '形态学/尿沉渣形态学', '2026-04-14 03:03:16.995197'),
('single', '<p>请选择下图箭头所指细胞名称<img src="/uploads/images/20260414_68aadc86c1af4630922243502550f2e7.png" alt="疟原虫.png" data-href="/uploads/images/20260414_68aadc86c1af4630922243502550f2e7.png" style=""/></p>', '{"A":"疟原虫","B":"肺孢子虫","C":"血小板","D":"畸形血小板"}', 'A', '', '形态学/寄生虫形态学', '2026-04-14 03:06:12.306928'),
('single', '<p>请选择下图箭头所指细胞名称：<img src="/uploads/images/20260414_438b902f1c9e4fabafd1816ede653ba8.png" alt="嗜多色性红细胞.png" data-href="/uploads/images/20260414_438b902f1c9e4fabafd1816ede653ba8.png" style=""/></p>', '{"A":"浆质体","B":"细胞核","C":"嗜多色红细胞","D":"淋巴细胞"}', 'C', '', '形态学/血细胞形态学', '2026-04-14 03:08:54.821560'),
('single', '<p>请选择下图箭头所指细胞名称：<img src="/uploads/images/20260414_910c8b77f1eb467bb42af4f8dfa80baa.png" alt="嗜碱性粒细胞.png" data-href="/uploads/images/20260414_910c8b77f1eb467bb42af4f8dfa80baa.png" style=""/></p>', '{"A":"中性粒细胞","B":"嗜碱性粒细胞","C":"嗜酸性粒细胞","D":"组织细胞"}', 'B', '', '形态学/血细胞形态学', '2026-04-14 03:19:13.264810'),
('single', '<p>请选择下图箭头所指细胞名称：<img src="/uploads/images/20260414_0a8625c36d8c419fb192f3917c7f460f.png" alt="夏科-雷登结晶.png" data-href="/uploads/images/20260414_0a8625c36d8c419fb192f3917c7f460f.png" style=""/></p>', '{"A":"夏科-雷登结晶","B":"植物细胞","C":"尿酸结晶","D":"滑石粉颗粒"}', 'A', '', '形态学/形态学', '2026-04-14 03:22:47.503737'),
('single', '<p>请选择下图细胞名称：<img src="/uploads/images/20260414_4c2e3cdc834045788c0dbd034bdf0b61.jpg" alt="异型淋巴细胞.jpg" data-href="/uploads/images/20260414_4c2e3cdc834045788c0dbd034bdf0b61.jpg" style=""/></p>', '{"A":"浆细胞","B":"单核细胞","C":"反应性淋巴细胞","D":"幼稚细胞"}', 'C', '', '形态学/血细胞形态学', '2026-04-14 04:28:58.283090'),
('single', '<p>请选择下图箭头所指细胞名称：<img src="/uploads/images/20260414_7a9015c401664b178161c8ff3a9abfa1.jpg" alt="原始单核细胞.jpg" data-href="/uploads/images/20260414_7a9015c401664b178161c8ff3a9abfa1.jpg" style="width: 100%;"/></p>', '{"A":"原始单核细胞","B":"原始粒细胞","C":"早幼粒细胞","D":"淋巴细胞"}', 'A', '', '形态学/血细胞形态学', '2026-04-14 04:38:08.108184'),
('single', '<p>请选择下图细胞名称：<img src="/uploads/images/20260414_40fcb760d79d4c3482418e7535e4923e.png" alt="中性中幼粒细胞.png" data-href="/uploads/images/20260414_40fcb760d79d4c3482418e7535e4923e.png" style=""/></p>', '{"A":"中性中幼粒细胞","B":"早幼粒细胞","C":"单核细胞","D":"成骨细胞"}', 'A', '', '形态学/血细胞形态学', '2026-04-14 04:40:36.004219'),
('single', '<p>请选择下图箭头所指细胞名称：<img src="/uploads/images/20260414_5adf412d79c5465c9da6274ef4214de8.png" alt="底层移行上皮细胞.png" data-href="/uploads/images/20260414_5adf412d79c5465c9da6274ef4214de8.png" style="width: 50%;"/></p>', '{"A":"鳞状上皮细胞","B":"底层移形上皮细胞","C":"复粒细胞","D":"肾小管上皮细胞"}', 'B', '', '形态学/尿沉渣形态学', '2026-04-14 04:52:45.078043'),
('single', '<p>请选择下图所示细胞名称<img src="/uploads/images/20260416_bb049a1737a6404983a174e04672c338.jpg" alt="" data-href="" style="width: 50%;"/></p>', '{"A":"多分叶中性粒细胞","B":"核分裂相","C":"骨髓瘤细胞","D":"异常早幼粒细胞"}', 'A', '', '形态学/细胞形态学', '2026-04-16 11:29:11.990128'),
('single', '<p>请选择下图所示细胞名称<img src="/uploads/images/20260416_29b8bbe7b4c143c9a48a8b5716022391.png" alt="" data-href="" style="width: 50%;"/></p>', '{"A":"疟原虫","B":"巨大血小板","C":"正常血小板","D":"嗜多色性红细胞"}', 'B', '', '形态学/细胞形态学', '2026-04-16 11:29:14.042791'),
('single', '<p>请选择下图所示细胞名称<img src="/uploads/images/20260416_b8c4196dbf73493eac3c6b5bd81e2729.png" alt="" data-href="" style="width: 50%;"/></p>', '{"A":"反应性淋巴细胞","B":"浆细胞","C":"单核细胞","D":"淋巴细胞"}', 'A', '', '形态学/细胞形态学', '2026-04-16 11:29:16.089509'),
('single', '<p>请选择下图所示细胞名称<img src="/uploads/images/20260416_c729169f91f8418d89a9f917535a037d.jpg" alt="" data-href="" style="width: 50%;"/></p>', '{"A":"异常早幼粒细胞","B":"多分叶中性粒细胞","C":"单核细胞","D":"浆细胞"}', 'A', '', '形态学/细胞形态学', '2026-04-16 11:29:18.134951'),
('single', '<p>请选择下图所示细胞名称<img src="/uploads/images/20260416_eb20c08a30e94a3fa258ad2fc2db0e9f.jpg" alt="" data-href="" style="width: 50%;"/></p>', '{"A":"巨核细胞","B":"浆细胞","C":"尼曼-皮克细胞","D":"组织细胞"}', 'B', '', '形态学/细胞形态学', '2026-04-16 11:29:20.172569'),
('single', '<p>请选择下图所示细胞名称</p><img src="/uploads/images/20260416_03be4780be7246b89f9acb28699a6da1.png" alt="" data-href="" style="width: 50%;"/>', '{"A":"红细胞管型","B":"颗粒管型","C":"透明管型","D":"粘液丝"}', 'B', '', '形态学/尿沉渣形态学', '2026-04-16 11:29:28.375868'),
('single', '<p>请选择下图所示细胞成分名称：<img src="/uploads/images/20260416_3678ea0e9307415d8fb720b58da0d5a9.jpg" alt="chediak-higashi颗粒.jpg" data-href="/uploads/images/20260416_3678ea0e9307415d8fb720b58da0d5a9.jpg" style="width: 50%;"/></p>', '{"A":"杜勒小体","B":"chediak-higashi颗粒","C":"绿色小体","D":"包涵体"}', 'B', '', '形态学/血细胞形态学', '2026-04-16 13:57:49.608158');

-- exams
INSERT INTO exams (title, duration, start_time, end_time, pass_score, single_score, multiple_score, judgment_score, retake_limit, total_score, created_by, created_at) VALUES
('医学基础测试', 90, '2026-04-14 00:00:00.000000', '2026-04-29 00:00:00.000000', 60, 15, 25, 10, 0, 15, 1, '2026-04-12 14:39:25.541835'),
('2026上半年杨思医院检验科形态学考核', 90, '2026-04-12 00:00:00.000000', '2026-05-31 00:00:00.000000', 60, 8, 20, 5, 0, 80, 1, '2026-04-12 14:51:41.055592'),
('医学检验', 60, '2026-04-13 00:00:00.000000', '2026-04-30 00:00:00.000000', 60, 6, 10, 4, 0, 100, 5, '2026-04-13 14:01:12.372333'),
('大方', 90, '2026-04-14 00:00:00.000000', '2026-04-29 00:00:00.000000', 60, 5, 20, 5, 0, 245, 5, '2026-04-14 14:31:43.942781'),
('当地', 90, NULL, NULL, 60, 5, 10, 5, 0, 225, 1, '2026-04-15 13:21:56.466753');

-- exam_question
INSERT INTO exam_question (exam_id, question_id) VALUES
(1, 14),
(2, 2), (2, 3), (2, 4), (2, 5), (2, 8), (2, 9), (2, 10), (2, 12), (2, 13), (2, 14),
(3, 2), (3, 3), (3, 4), (3, 5), (3, 8), (3, 9), (3, 10), (3, 12), (3, 13), (3, 14), (3, 18), (3, 19), (3, 20), (3, 21), (3, 22), (3, 23),
(4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 15), (4, 16), (4, 17), (4, 20), (4, 21), (4, 26), (4, 29), (4, 30), (4, 31), (4, 33), (4, 35), (4, 38), (4, 39), (4, 40), (4, 42),
(5, 2), (5, 9), (5, 10), (5, 13), (5, 18), (5, 19), (5, 20), (5, 21), (5, 24), (5, 25), (5, 26), (5, 27), (5, 31), (5, 32), (5, 35), (5, 36), (5, 37), (5, 39);

-- exam_records
INSERT INTO exam_records (exam_id, user_id, answers, score, total_score, submitted_at) VALUES
(3, 5, '{"2":"C","3":"D","4":"C","5":"C","6":"B","7":"C","8":"A","9":"D","10":"D","11":"A","12":"C","13":"B","14":"A","18":"B","19":"正确","20":"A","21":"C"}', 100.0, 100.0, '2026-04-13 14:15:38.356566'),
(3, 2, '{"2":"B","3":"D","4":"B","5":"B","6":"B","7":"C","8":"A","9":"D","10":"D","11":"A","12":"C","13":"B","14":"C","18":"B","19":"错误","20":"B","21":"B"}', 60.0, 100.0, '2026-04-13 14:18:20.893589'),
(2, 1, '{"2":"B","3":"D","4":"C","5":"B","6":"C","7":"C","8":"C","9":"B","10":"B","11":"C","12":"C","13":"D","14":"D"}', 32.0, 104.0, '2026-04-13 14:21:21.854016'),
(1, 2, '{"14":"A"}', 15.0, 15.0, '2026-04-14 10:57:11.360771'),
(2, 2, '{"2":"C","3":"D","4":"C","5":"C","8":"A","9":"D","10":"D","12":"C","13":"B","14":"A"}', 80.0, 80.0, '2026-04-14 10:58:40.758506'),
(NULL, 1, '{"1":"A","2":"C","3":"D","4":"C","8":"A","13":"B","14":"A","15":"A","17":"A","29":"A","31":"C","33":"D","36":"A","38":"A","42":"B"}', 65.0, 75.0, '2026-04-14 14:24:34.917364'),
(4, 5, '{"5":"C","8":"A","9":"D","10":"D","14":"A","21":"C","37":"B","39":"C","40":"A","41":"A"}', 100.0, 100.0, '2026-04-14 14:38:58.659458'),
(5, 1, '{"2":"C","9":"D","10":"D","13":"B","18":"B","19":"正确","20":"A","21":"C","24":"A,B,C,D","25":"A,B,C,E","26":"A","27":"A","31":"C","32":"B","35":"A","36":"A","37":"B","39":"C"}', 95.0, 100.0, '2026-04-15 13:24:34.498253'),
(1, 6, '{"14":"A"}', 15.0, 15.0, '2026-04-15 14:54:55.993846'),
(2, 2, '{"2":"C","3":"D","4":"C","5":"C","8":"A","9":"D","10":"D","12":"C","13":"B","14":"A"}', 80.0, 80.0, '2026-04-16 14:43:26.108674');

-- exam_distributions (邀请码, 考试无需邀请码也能参加)
INSERT INTO exam_distributions (exam_id, user_id, invite_code, created_at) VALUES
(5, 1, 'A9S3QW', '2026-04-16 14:21:40.148850'),
(2, 2, 'MPLG2M', '2026-04-16 14:26:19.742523'),
(2, 3, 'U1IR5T', '2026-04-16 14:26:19.742527'),
(2, 4, '9U57H1', '2026-04-16 14:26:19.742529'),
(2, 5, 'JKD4NR', '2026-04-16 14:26:19.742531'),
(2, 6, 'M0H7C2', '2026-04-16 14:26:19.742532'),
(5, 2, '4NX0OI', '2026-04-16 14:29:59.307288'),
(5, 3, '76RUYZ', '2026-04-16 14:29:59.307292'),
(5, 4, '2U7XLS', '2026-04-16 14:29:59.307293'),
(5, 5, '2CKWI8', '2026-04-16 14:29:59.307295'),
(5, 6, 'KLTJ0G', '2026-04-16 14:29:59.307296');

-- ===================== VERIFY =====================
SELECT 'Users: ' || COUNT(*)::text FROM users
UNION ALL SELECT 'Questions: ' || COUNT(*)::text FROM questions
UNION ALL SELECT 'Exams: ' || COUNT(*)::text FROM exams
UNION ALL SELECT 'ExamQuestion: ' || COUNT(*)::text FROM exam_question
UNION ALL SELECT 'ExamRecords: ' || COUNT(*)::text FROM exam_records
UNION ALL SELECT 'Distributions: ' || COUNT(*)::text FROM exam_distributions;
