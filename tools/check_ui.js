#!/usr/bin/env node
// Έλεγχος του detector_academic.html χωρίς browser (τρέχει στο CI):
//  1. το inline <script> είναι συντακτικά σωστό JavaScript
//  2. κάθε γλώσσα του LANGUAGES έχει μπλοκ στο STRINGS με ΟΛΑ τα κλειδιά των αγγλικών
//  3. τα placeholders ({n}, {total}, ...) είναι ίδια σε όλες τις μεταφράσεις
//  4. κάθε κλειδί που χρησιμοποιεί η σελίδα (t('...'), data-i18n="...") υπάρχει
//  5. κανένα κείμενο δεν έχει <script> ή on...= (τα data-i18n-html μπαίνουν ως innerHTML)
//  6. καμία συνάρτηση δεν δηλώνεται δύο φορές (η δεύτερη «σκεπάζει» σιωπηλά την πρώτη)
// Χρήση: node tools/check_ui.js [path/to/detector_academic.html]

'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const file = process.argv[2] || path.join(__dirname, '..', 'detector_academic.html');
const html = fs.readFileSync(file, 'utf8');
const errors = [];

const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (scripts.length === 0) errors.push('Δεν βρέθηκε inline <script>');
scripts.forEach((code, i) => {
    const seen = new Map();
    for (const m of code.matchAll(/^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/gm)) {
        seen.set(m[1], (seen.get(m[1]) || 0) + 1);
    }
    for (const [name, n] of seen) {
        if (n > 1) errors.push(`Η συνάρτηση ${name}() δηλώνεται ${n} φορές στο inline script #${i}`);
    }
    try {
        new vm.Script(code, { filename: `inline-script-${i}.js` });
    } catch (e) {
        errors.push(`Συντακτικό λάθος στο inline script #${i}: ${e.message}`);
    }
});

function extractObject(name) {
    const m = html.match(new RegExp(`const ${name} = (\\{[\\s\\S]*?\\n        \\});`));
    if (!m) throw new Error(`Δεν βρέθηκε το ${name}`);
    return vm.runInNewContext('(' + m[1] + ')');
}

let STRINGS, LANGUAGES;
try {
    STRINGS = extractObject('STRINGS');
    LANGUAGES = extractObject('LANGUAGES');
} catch (e) {
    errors.push(e.message);
}

if (STRINGS && LANGUAGES) {
    const base = STRINGS.en;
    if (!base) errors.push('Λείπουν τα αγγλικά (STRINGS.en) — είναι η γλώσσα-βάση');
    const baseKeys = Object.keys(base || {});
    const placeholders = s => (String(s).match(/\{\w+\}/g) || []).sort().join(',');

    for (const lang of Object.keys(LANGUAGES)) {
        const block = STRINGS[lang];
        if (!block) { errors.push(`Η γλώσσα "${lang}" δεν έχει μπλοκ στο STRINGS`); continue; }
        for (const k of baseKeys) {
            if (!(k in block)) errors.push(`[${lang}] λείπει το κλειδί "${k}"`);
            else if (placeholders(block[k]) !== placeholders(base[k]))
                errors.push(`[${lang}] "${k}": placeholders ${placeholders(block[k])} ≠ ${placeholders(base[k])}`);
        }
        for (const k of Object.keys(block)) {
            if (!(k in base)) errors.push(`[${lang}] περιττό κλειδί "${k}" (δεν υπάρχει στα αγγλικά)`);
            if (/<script|\son\w+\s*=|javascript:/i.test(block[k]))
                errors.push(`[${lang}] "${k}": ύποπτο HTML (script/on…=/javascript:)`);
        }
    }
    for (const lang of Object.keys(STRINGS)) {
        if (!LANGUAGES[lang]) errors.push(`Το STRINGS.${lang} δεν έχει εγγραφή στο LANGUAGES`);
    }

    const used = new Set([
        // μόνο πλήρη κλειδιά — όχι προθέματα όπως t('ref_status_' + code)
        ...[...html.matchAll(/\bt\(\s*'([a-z0-9_]+)'\s*[,)]/g)].map(m => m[1]),
        ...[...html.matchAll(/data-i18n(?:-html|-placeholder)?="([a-z0-9_]+)"/g)].map(m => m[1]),
    ]);
    for (const k of used) {
        if (!(k in (base || {}))) errors.push(`Χρησιμοποιείται το κλειδί "${k}" αλλά δεν ορίζεται`);
    }
    if (!errors.length) {
        console.log(`✅ ${Object.keys(LANGUAGES).length} γλώσσες × ${baseKeys.length} κλειδιά, ` +
                    `${used.size} κλειδιά σε χρήση, ${scripts.length} script(s) OK`);
    }
}

if (errors.length) {
    errors.forEach(e => console.error('❌ ' + e));
    process.exit(1);
}
