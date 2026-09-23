const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || '';

module.exports = {
  expo: {
    name: 'AI Trading Paper',
    slug: 'ai-trading-paper',
    version: '1.8.0',
    orientation: 'portrait',
    userInterfaceStyle: 'dark',
    newArchEnabled: true,
    android: {
      package: 'com.aitrading.paper',
      versionCode: 9,
      adaptiveIcon: {
        foregroundImage: './assets/adaptive-icon.png',
        backgroundColor: '#0b1020'
      },
      permissions: ['INTERNET']
    },
    ios: {
      bundleIdentifier: 'com.aitrading.paper',
      buildNumber: '9'
    },
    extra: {
      apiBaseUrl
    }
  }
};
