const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
  plugins: [
    new CopyPlugin({
      patterns: [
        {
          from: 'src/xpython_wasm.wasm',
          to: '.'
        },
        {
          from: 'src/xpython_wasm.js',
          to: '.'
        },
        {
          from: 'src/python_data.js',
          to: '.'
        },
        {
          from: 'src/*.data',
          to: './[name].data'
        },
        {
          from: 'src/*.js',
          to: './[name].js'
        },
      ]
    })
  ]
};
