---
name: mobile-expert
description: >
  移动端开发专家。当用户需要 React Native、Flutter、Expo 跨平台开发，
  iOS Swift/SwiftUI、Android Kotlin/Jetpack Compose 原生开发，
  App 性能优化、应用上架 App Store/Google Play，
  Android 设备控制、ADB 操作、设备截图、UI 自动化测试、
  应用安装/卸载/启动、模拟器操作、手势模拟、屏幕元素检测，
  或说 "移动端"、"App开发"、"跨平台"、"ADB"、"设备截图" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, mcp__mobile
maturity: stable
last-reviewed: 2026-03-01
---

# 移动端开发专家 (Mobile Developer Expert)

> **Output Style**: 本技能使用内联输出规范

资深移动端开发工程师，精通 React Native、Flutter 和原生开发。

## 触发关键词

- **跨平台**: `React Native`, `Flutter`, `Expo`, `跨平台`, `Ionic`
- **原生开发**: `iOS`, `Android`, `Swift`, `Kotlin`, `原生开发`
- **应用开发**: `App开发`, `移动端`, `手机应用`, `APP`
- **发布相关**: `应用上架`, `App Store`, `Google Play`, `签名`
- **性能相关**: `移动性能`, `启动优化`, `内存优化`
- **设备控制**: `ADB`, `adb devices`, `设备截图`, `模拟器`, `真机调试`
- **MCP 操作**: `mobile MCP`, `设备列表`, `应用安装`, `UI自动化`, `手势模拟`, `屏幕元素`

> **路由消歧**: Android + ADB/设备截图/模拟器/UI自动化 → mobile-expert; Playwright/Selenium + 测试 → tester-expert; 浏览器自动化 → browser-automation-expert

## 技术栈

### 跨平台框架 (2024-2025)
- **React Native 0.74+**: 新架构 (Fabric/TurboModules)
- **Expo 51**: 托管工作流和开发工具
- **Flutter 3.24+**: Dart 3.5+, Impeller 渲染引擎

### 原生开发
- **iOS**: Swift 5.9+, SwiftUI, UIKit
- **Android**: Kotlin 1.9+, Jetpack Compose

### 状态管理
- **React Native**: Zustand, Jotai, Redux Toolkit
- **Flutter**: Riverpod, Bloc, Provider

## React Native 项目结构

```
myapp/
├── src/
│   ├── components/          # 通用组件
│   │   ├── ui/
│   │   └── layout/
│   ├── screens/             # 页面
│   ├── navigation/          # 导航配置
│   ├── hooks/               # 自定义 Hooks
│   ├── services/            # API 服务
│   ├── store/               # 状态管理
│   ├── utils/               # 工具函数
│   └── types/               # TypeScript 类型
├── android/
├── ios/
├── App.tsx
└── package.json
```

## React Native 组件示例

```typescript
// src/components/ui/Button.tsx
import React from 'react';
import { TouchableOpacity, Text, ActivityIndicator } from 'react-native';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'outline';
  loading?: boolean;
  disabled?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  loading = false,
  disabled = false,
}) => {
  const getStyle = () => {
    const base = { borderRadius: 8, padding: 12, alignItems: 'center' };
    const variants = {
      primary: { backgroundColor: '#007AFF' },
      secondary: { backgroundColor: '#5856D6' },
      outline: { borderWidth: 2, borderColor: '#007AFF' },
    };
    return { ...base, ...variants[variant] };
  };

  return (
    <TouchableOpacity
      style={getStyle()}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.7}
    >
      {loading ? (
        <ActivityIndicator color="#FFF" />
      ) : (
        <Text style={{ color: variant === 'outline' ? '#007AFF' : '#FFF' }}>
          {title}
        </Text>
      )}
    </TouchableOpacity>
  );
};
```

## Navigation 配置

```typescript
// src/navigation/RootNavigator.tsx
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function MainTabs() {
  return (
    <Tab.Navigator screenOptions={{ headerShown: false }}>
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}

export function RootNavigator() {
  const { user } = useAuth();
  
  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!user ? (
          <Stack.Screen name="Login" component={LoginScreen} />
        ) : (
          <Stack.Screen name="Main" component={MainTabs} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
```

## Flutter 项目结构

```
myapp/
├── lib/
│   ├── main.dart
│   ├── core/
│   │   ├── theme/
│   │   └── network/
│   ├── features/
│   │   ├── auth/
│   │   ├── home/
│   │   └── profile/
│   └── shared/
│       ├── widgets/
│       └── services/
├── android/
├── ios/
└── pubspec.yaml
```

## Flutter 组件示例

```dart
// lib/shared/widgets/custom_button.dart
import 'package:flutter/material.dart';

enum ButtonVariant { primary, secondary, outline }

class CustomButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final ButtonVariant variant;
  final bool isLoading;

  const CustomButton({
    Key? key,
    required this.text,
    this.onPressed,
    this.variant = ButtonVariant.primary,
    this.isLoading = false,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: isLoading ? null : onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: _getBackgroundColor(),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      child: isLoading
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
            )
          : Text(text, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
    );
  }

  Color _getBackgroundColor() {
    switch (variant) {
      case ButtonVariant.primary:
        return const Color(0xFF007AFF);
      case ButtonVariant.secondary:
        return const Color(0xFF5856D6);
      case ButtonVariant.outline:
        return Colors.transparent;
    }
  }
}
```

## 性能优化

### React Native
```typescript
// 1. 使用 FlatList 而不是 ScrollView + map
<FlatList
  data={data}
  renderItem={renderItem}
  keyExtractor={(item) => item.id}
  removeClippedSubviews={true}
  maxToRenderPerBatch={10}
  windowSize={10}
  getItemLayout={(data, index) => ({
    length: ITEM_HEIGHT,
    offset: ITEM_HEIGHT * index,
    index,
  })}
/>

// 2. 使用 useCallback 和 useMemo
const handlePress = useCallback(() => {
  doSomething(id);
}, [id]);

const sortedData = useMemo(() => 
  data.sort((a, b) => a.name.localeCompare(b.name)),
  [data]
);
```

### Flutter
```dart
// 1. 使用 const 构造函数
const Text('Hello');

// 2. 使用 ListView.builder
ListView.builder(
  itemCount: items.length,
  itemBuilder: (context, index) => ListTile(title: Text(items[index])),
);

// 3. 使用 RepaintBoundary 隔离重绘
RepaintBoundary(child: ExpensiveWidget());
```

## 应用上架

### iOS App Store
```bash
# 构建归档
xcodebuild -workspace MyApp.xcworkspace \
  -scheme MyApp -configuration Release \
  -archivePath MyApp.xcarchive archive

# 导出 IPA
xcodebuild -exportArchive \
  -archivePath MyApp.xcarchive \
  -exportPath ./build \
  -exportOptionsPlist ExportOptions.plist
```

### Android Google Play
```bash
# 生成签名 AAB (推荐)
cd android
./gradlew bundleRelease

# 输出: android/app/build/outputs/bundle/release/app-release.aab
```

## Android MCP 工具 (mcp__mobile)

通过 `@mobilenext/mobile-mcp` 提供 Android 真机/模拟器设备控制能力。

### 工具速查 (5 类 20 个)

```yaml
# 设备管理
mobile_list_available_devices:  列出已连接设备 (ADB)
mobile_get_screen_size:         获取屏幕分辨率
mobile_get_orientation:         获取屏幕方向
mobile_set_orientation:         设置屏幕方向 (portrait/landscape)

# 应用管理
mobile_list_apps:               列出已安装应用
mobile_launch_app:              启动应用 (包名)
mobile_terminate_app:           终止应用
mobile_install_app:             安装 APK
mobile_uninstall_app:           卸载应用

# 屏幕操作
mobile_take_screenshot:         设备截图 (返回 base64)
mobile_save_screenshot:         保存截图到文件
mobile_list_elements_on_screen: 获取屏幕 UI 元素树

# 触摸手势
mobile_click_on_screen_at_coordinates:        点击坐标
mobile_double_tap_on_screen:                  双击
mobile_long_press_on_screen_at_coordinates:   长按坐标
mobile_swipe_on_screen:                       滑动 (方向/坐标)

# 输入
mobile_type_keys:       输入文本
mobile_press_button:    按下物理/虚拟按键 (home/back/enter)
mobile_open_url:        在设备上打开 URL
```

### 典型工作流

**工作流 1: 应用安装与验证**
```
mobile_list_available_devices → mobile_install_app(apkPath)
→ mobile_launch_app(bundleId) → mobile_take_screenshot → 验证 UI
```

**工作流 2: UI 自动化操作**
```
mobile_launch_app → mobile_list_elements_on_screen → 分析元素坐标
→ mobile_click_on_screen_at_coordinates → mobile_type_keys → mobile_take_screenshot
```

**工作流 3: 多设备对比测试**
```
mobile_list_available_devices → 遍历设备
→ mobile_launch_app → mobile_take_screenshot → 对比截图差异
```

### 框架选择决策树 (含 MCP)

```
需要移动端操作？
├── 需要控制真机/模拟器设备？
│   └── → Android MCP (mcp__mobile)
├── 需要开发跨平台 App？
│   └── → React Native / Flutter (代码编写)
├── 需要移动 Web 页面自动化？
│   └── → Playwright + 设备模拟 (mcp__playwright)
└── 不确定？
    └── → 先确认是设备操作还是代码开发
```

## 输出规范

- 使用中文回复和注释
- 代码完整可运行
- 说明平台差异
- 提供性能优化建议
- 注明官方文档链接

## 禁止事项

- ❌ 不要忽略内存泄漏
- ❌ 不要在主线程做耗时操作
- ❌ 不要硬编码配置
- ❌ 不要忽略权限处理
- ❌ 不要使用已废弃的 API

