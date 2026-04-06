const fs = require('fs');

const file = '/Users/sunshuwen/AI_code/cryptoquant/agno-chat-ui/src/pages/SettingsPage.jsx';

if (fs.existsSync(file)) {
    let content = fs.readFileSync(file, 'utf8');
    
    // 主题色替换
    content = content.replace(/indigo/g, 'emerald');
    content = content.replace(/violet/g, 'teal');
    content = content.replace(/blue-500/g, 'teal-500');
    content = content.replace(/purple-500/g, 'teal-500');
    
    // 背景色替换
    content = content.replace(/#131722/g, '#0e1215');
    content = content.replace(/#1a1f2e/g, '#0a0d0f');
    content = content.replace(/#1c2230/g, '#111516');
    content = content.replace(/#0B0E11/g, '#060809');
    content = content.replace(/#1C2127/g, '#0A0D0F');
    
    fs.writeFileSync(file, content);
    console.log(`Updated ${file}`);
} else {
    console.log(`File not found: ${file}`);
}
