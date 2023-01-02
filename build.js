const { execSync } = require('child_process');
const which = require('which');
const { copyFileSync } = require('fs');

const PYTHON_VERSION = '3.10';

let command = null;

try {
    command = which.sync('micromamba');
    console.log('[xeus-python] Creating emscripten env with micromamba');
} catch (err) {
    try {
        command = which.sync('mamba');
        console.log('[xeus-python] Creating emscripten env with mamba');
    } catch (err) {
        try {
            command = which.sync('conda');
            console.log('[xeus-python] Creating emscripten env with conda');
        } catch (err) {}
    }
}

/**
 * Create the Emscripten env and pack it.
 */
function build() {
    // Create env
    execSync(`
        ${command} create -n xeus-python-kernel \
            --platform=emscripten-32 \
            --root-prefix=/tmp/xeus-python-kernel \
            -c https://repo.mamba.pm/emscripten-forge \
            -c https://repo.mamba.pm/conda-forge \
            --yes \
            python=${PYTHON_VERSION} xeus-python xeus-lite
    `);

    // Copy xeus-python output
    copyFileSync('/tmp/xeus-python-kernel/envs/xeus-python-kernel/bin/xpython_wasm.js', 'src');
    copyFileSync('/tmp/xeus-python-kernel/envs/xeus-python-kernel/bin/xpython_wasm.wasm', 'src');

    // Pack env
    execSync('empack pack env --env-prefix /tmp/xeus-python-kernel/envs/xeus-python-kernel --outname src/python_data');
}

if (require.main === module) {
    build();
}
