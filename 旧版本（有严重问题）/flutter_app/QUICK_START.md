# 快速启动指南

## 🚀 5分钟快速开始

### 前提条件
确保已安装：
- Flutter SDK (3.0+)
- 目标平台开发工具 (如 Windows 需要 Visual Studio)

### 步骤 1: 进入项目目录
```bash
cd flutter_app
```

### 步骤 2: 获取依赖
```bash
flutter pub get
```

### 步骤 3: 运行项目

**Windows 用户：**
```bash
flutter run -d windows
```

**macOS 用户：**
```bash
flutter run -d macos
```

**Linux 用户：**
```bash
flutter run -d linux
```

**Android 用户：**
```bash
flutter run -d android
```

**iOS 用户：**
```bash
flutter run -d ios
```

**Web 用户：**
```bash
flutter run -d chrome
```

### 步骤 4: 构建发布版本 (可选)

**构建 Windows 应用：**
```bash
flutter build windows --release
```
构建产物位置：`build\windows\runner\Release\`

**构建 Android APK：**
```bash
flutter build apk --release
```
构建产物位置：`build\app\outputs\flutter-apk\app-release.apk`

## 📱 功能使用指南

### 基本操作流程

1. **选择输入目录**
   - 点击左侧边栏底部"输入目录"
   - 选择包含图片的文件夹

2. **选择输出目录**
   - 点击"输出目录"
   - 选择处理结果保存位置

3. **选择功能页面**
   - 首页 - 查看功能介绍
   - 一条龙模式 - 一键完成所有操作
   - 格式转换 - 转换图片格式
   - 重复检测 - 找出重复图片
   - 批量重命名 - 批量改名
   - 分类整理 - 自动分类

4. **扫描图片**
   - 点击"扫描图片"按钮
   - 等待扫描完成

5. **执行操作**
   - 根据页面提示配置参数
   - 点击对应功能按钮执行

### 一条龙模式使用示例

1. 切换到"一条龙模式"页面
2. 配置每个步骤（可选）：
   - 去重检测：相似度阈值、保留策略
   - 格式转换：输出格式、质量
   - 分类整理：比例、形状分类
   - 批量重命名：命名模板
3. 点击"开始执行"
4. 等待处理完成

## 🔧 常见问题

### Q: 无法选择文件夹？
A: 确保 `file_picker` 依赖正确安装，运行 `flutter pub get`

### Q: 编译错误？
A: 运行以下命令清理并重新构建：
```bash
flutter clean
flutter pub get
flutter run
```

### Q: 图片处理慢？
A: 首次运行需要解码图片，后续会使用缓存

### Q: 如何查看日志？
A: 每个功能页面底部都会显示操作日志

### Q: 支持哪些图片格式？
A: JPG, JPEG, PNG, WebP, BMP, GIF, TIFF, TIF, ICO

## 📖 更多文档

- `README.md` - 项目介绍和功能说明
- `MIGRATION_GUIDE.md` - 从 Python 迁移的详细指南
- `PROJECT_SUMMARY.md` - 完整的项目总结和技术细节

## 💡 提示

- 建议先在测试文件夹中试用，熟悉功能后再处理重要文件
- "一条龙模式"是最便捷的方式，适合批量处理
- 所有操作都会输出到选择的"输出目录"，不会修改原文件
- 可以启用"递归子目录"选项处理子文件夹中的图片

---

享受你的新图片处理工具吧！🎉
