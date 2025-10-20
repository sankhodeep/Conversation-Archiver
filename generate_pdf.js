const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

/**
 * Generates a PDF from a temporary HTML file using Puppeteer.
 *
 * This script is called by the Python `pdf_engine.py`. It launches a headless
 * Chrome browser, reads the content from `_temp.html`, renders it, and saves
 * it as `_temp_page.pdf`. The Python script is responsible for creating the
 * HTML file and for renaming and moving the final PDF.
 *
 * @async
 * @function generatePdf
 * @returns {Promise<void>} A promise that resolves when the PDF is generated.
 * @throws Will exit the process with code 1 if an error occurs.
 */
async function generatePdf() {
    try {
        const browser = await puppeteer.launch({
            headless: "new",
        });
        const page = await browser.newPage();

        // The Python script will create this temporary HTML file
        const htmlFilePath = path.resolve(__dirname, '_temp.html');
        const htmlContent = fs.readFileSync(htmlFilePath, 'utf8');

        // Set the page content and wait for all fonts to load from Google Fonts
        await page.setContent(htmlContent, {
            waitUntil: 'networkidle0'
        });

        // Generate the PDF
        await page.pdf({
            path: '_temp_page.pdf', // The Python script will look for this file
            format: 'A4',
            printBackground: true,
        });

        await browser.close();
        console.log('PDF page generated successfully by Puppeteer.');

    } catch (err) {
        console.error('Error generating PDF with Puppeteer:', err);
        process.exit(1); // Exit with an error code
    }
}

generatePdf();