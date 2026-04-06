# 图片工具 - Image Tool

简洁高效的跨平台图片处理工具

## 功能特性

### 🔄 格式转换
- 支持 JPG、PNG、WebP、ICO 格式互转
- 质量调节 (1-100)
- PNG3 压缩支持
- ICO 多尺寸生成
- 同格式也重编码选项

### 🔍 重复检测
- 感知哈希算法 (aHash/dHash)
- 汉明距离计算
- 相似度阈值可调
- 多种保留策略:
  - 首个文件
  - 最大分辨率
  - 最大文件
  - 最新/最旧文件
- 处理动作: 仅列出/删除/移动

### ✏️ 批量重命名
- 灵活的命名模板
- 序号配置 (起始/步长/宽度)
- 实时预览功能
- 覆盖策略选择

### 📁 分类整理
- 按宽高比例分类
- 按形状分类 (方形/横向/纵向)
- 预设比例快速选择
- 容差调节
- 自定义文件夹名称

## 技术栈

| 类别 | 技术 |
|------|------|
| UI 框架 | Flutter 3.x |
| 编程语言 | Dart 3.x |
| 状态管理 | Provider |
| 图片处理 | image |
| 文件选择 | file_picker |
| 哈希计算 | crypto |

## 快速开始

### 安装依赖
```bash
flutter pub get
```

### 运行开发模式
```bash
# Windows
flutter run -d windows

# macOS
flutter run -d macos

# Linux
flutter run -d linux
```

### 构建发布版本
```bash
# Windows
flutter build windows --release

# macOS
flutter build macos --release

# Linux
flutter build linux --release
```

## 项目结构

```
lib/
├── main.dart                    # 应用入口
├── core/                        # 核心业务逻辑
│   ├── image_service.dart      # 图片处理服务
│   └── file_service.dart       # 文件操作服务
├── models/                      # 数据模型
│   └── image_info.dart         # 图片信息模型
├── providers/                   # 状态管理
│   ├── convert_state.dart      # 转换状态
│   ├── dedupe_state.dart       # 去重状态
│   ├── rename_state.dart       # 重命名状态
│   └── classify_state.dart     # 分类状态
└── ui/                          # 用户界面
    ├── main_window.dart        # 主窗口
    ├── theme.dart              # 主题配置
    ├── pages/                  # 功能页面
    │   ├── convert_page.dart
    │   ├── dedupe_page.dart
    │   ├── rename_page.dart
    │   └── classify_page.dart
    └── widgets/                # 通用组件
        └── common.dart
```

## UI 设计

### 设计原则
- **简洁** - 去除冗余元素，聚焦核心功能
- **现代** - Material Design 3 规范
- **一致** - 统一的视觉语言
- **高效** - 清晰的信息层级

### 布局架构
- 左侧边栏导航 (220px)
- 右侧动态内容区
- 卡片式设计组织内容
- 亮色/暗色主题支持

### 色彩系统
- 主色: 靛蓝色 (#4F46E5)
- 成功色: 绿色 (#10B981)
- 警告色: 琥珀色 (#F59E0B)
- 错误色: 红色 (#EF4444)

## 代码质量

### 静态分析
```bash
flutter analyze
```

### 格式化
```bash
dart format .
```

## 依赖说明

### 核心依赖
- `provider`: 状态管理
- `image`: 图片处理核心库
- `file_picker`: 文件/目录选择
- `path`: 路径操作
- `crypto`: 哈希计算

### 开发依赖
- `flutter_lints`: 代码规范检查
- `build_runner`: 代码生成

## 已知限制

1. **回收站删除** - Flutter 暂不支持跨平台回收站，目前为直接删除
2. **大图片处理** - 可能需要内存优化
3. **动画图片** - 部分功能对动画图片支持有限

## 开发计划

### 短期
- [ ] 添加单元测试
- [ ] 优化大图片处理性能
- [ ] 改进错误处理

### 中期
- [ ] 添加更多图片格式支持 (AVIF, HEIC)
- [ ] 多线程并发处理
- [ ] 操作历史记录

### 长期
- [ ] Rust 后端集成 (FFI)
- [ ] GPU 加速
- [ ] 插件系统

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request!

---

**版本**: 1.0.0  
**更新时间**: 2026年4月
