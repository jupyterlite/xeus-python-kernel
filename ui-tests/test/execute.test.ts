// Copyright (c) JupyterLite Contributors
// Distributed under the terms of the Modified BSD License.

import { test } from '@jupyterlab/galata';

import { expect } from '@playwright/test';

import { firefoxWaitForApplication } from './utils';

test.use({ waitForApplication: firefoxWaitForApplication });

test.describe('Code execution', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('lab/index.html');
  });

  test('Basic code execution', async ({ page }) => {
    await page.notebook.createNew();
    await page.notebook.setCell(0, 'code', '2 + 2');
    await page.notebook.run();
    const output = await page.notebook.getCellTextOutput(0);

    expect(output).toBeTruthy();
    expect(output![0]).toBe('4');
  });

  test('Import critical packages', async ({ page }) => {
    await page.notebook.createNew();
    await page.notebook.setCell(0, 'code', 'import scipy\nscipy.__version__');
    await page.notebook.run();
    const output = await page.notebook.getCellTextOutput(0);

    expect(output).not.toContain('ModuleNotFoundError');
  });
});
