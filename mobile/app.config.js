const base = require('./app.config.base.js');

module.exports = (ctx) => {
  const config = typeof base === 'function' ? base(ctx) : base;

  if (config.expo) {
    return {
      ...config,
      expo: {
        ...config.expo,
        android: {
          ...(config.expo.android || {}),
          versionCode: 10607
        },
        extra: {
          ...(config.expo.extra || {}),
          eas: {
            ...(config.expo.extra?.eas || {}),
            projectId: '6b391d57-adb3-4440-afa1-734afbffba72'
          }
        }
      }
    };
  }

  return {
    ...config,
    android: {
      ...(config.android || {}),
      versionCode: 10607
    },
    extra: {
      ...(config.extra || {}),
      eas: {
        ...(config.extra?.eas || {}),
        projectId: '6b391d57-adb3-4440-afa1-734afbffba72'
      }
    }
  };
};
