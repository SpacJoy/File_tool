# 图片批量处理工具 (Flutter 版本)

一个功能完善的图片批量处理工具，支持去重、格式转换、分类整理和批量重命名。

## 功能特性

### 一条龙模式
按顺序执行所有操作，一站式批量处理解决方案。

### 格式转换
- 支持 JPG/PNG/WebP/ICO 格式互转
- 质量调节 (1-100)
- PNG3 压缩支持
- ICO 多尺寸生成 (16/32/48/64/128/256)
- 非方图处理 (保持/中心裁切/左上裁切/等比填充)

### 重复检测
- 感知哈希算法 (aHash/dHash)
- 相似度阈值可调 (0-32)
- 多种保留策略 (首个/最大分辨率/最大文件/最新/最旧)
- 支持删除或移动重复文件

### 批量重命名
- 灵活的命名模板 ({name}, {ext}, {fmt}, {index})
- 序号配置 (起始/步长/宽度)
- 按格式分组编号

### 分类整理
- 按宽高比例分类 (16:9, 16:10, 4:3, 3:2, 5:4, 21:9, 1:1)
- 自定义比例支持
- 按形状分类 (方形/横向/纵向)
- 动画图片自动识别

## 安装依赖

```bash
flutter pub get
```

## 运行

```bash
flutter run
```

## 构建

### Windows
```bash
flutter build windows
```

### macOS
```bash
flutter build macos
```

### Linux
```bash
flutter build linux
```

### Android
```bash
flutter build apk
```

### iOS
```bash
flutter build ios
```

## 技术栈

- **Flutter** - UI 框架
- **Provider** - 状态管理
- **image** - 图片处理库
- **file_picker** - 文件选择
- **crypto** - 哈希计算

## 开发

```bash
# 分析代码
flutter analyze

# 运行测试
flutter test

# 格式化代码
flutter format .
```

## 许可

MIT License
