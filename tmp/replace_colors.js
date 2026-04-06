const fs = require('fs');

const files = [
    '/Users/sunshuwen/AI_code/cryptoquant/agno-chat-ui/src/components/SettingsModal.jsx',
    '/Users/sunshuwen/AI_code/cryptoquant/agno-chat-ui/src/pages/ExecutionPage.jsx'
];

files.forEach(file => {
    if (fs.existsSync(file)) {
        let content = fs.readFileSync(file, 'utf8');
        // 主题色替换
        content = content.replace(/indigo/g, 'emerald');
        content = content.replace(/violet/g, 'teal');
        // 极暗黑背景调整
        content = content.replace(/#131722/g, '#0e1215');
        content = content.replace(/#1a1f2e/g, '#0a0d0f');
        content = content.replace(/#1c2230/g, '#111516');
        fs.writeFileSync(file, content);
        console.log(`Updated ${file}`);
    } else {
        console.log(`File not found: ${file}`);
    }
});
