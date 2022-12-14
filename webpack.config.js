const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
  plugins: [
    new CopyPlugin({
      patterns: [
        {
          from: 'src/*.wasm',
          to: '.'
        },
        {
          from: 'src/*.data',
          to: '.'
        },
        {
          from: 'src/*.js',
          to: '.'
        }
      ]
    })
  ]
};
