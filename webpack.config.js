const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
  plugins: [
    new CopyPlugin({
      patterns: [
        {
          from: 'src/*.wasm',
          to: '[name][ext]'
        },
        {
          from: 'src/*.data',
          to: '[name][ext]'
        },
        {
          from: 'src/*.js',
          to: '[name][ext]'
        }
      ]
    })
  ]
};
