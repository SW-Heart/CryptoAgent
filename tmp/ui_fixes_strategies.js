const fs = require('fs');

const file = '/Users/sunshuwen/AI_code/cryptoquant/agno-chat-ui/src/pages/StrategiesPage.jsx';

if (fs.existsSync(file)) {
    let content = fs.readFileSync(file, 'utf8');
    
    // 基础颜色替换
    content = content.replace(/indigo/g, 'emerald');
    content = content.replace(/violet/g, 'teal');
    content = content.replace(/blue/g, 'teal');
    content = content.replace(/purple/g, 'teal');
    
    // 背景色替换
    content = content.replace(/#131722/g, '#0e1215');
    content = content.replace(/#1a1f2e/g, '#0a0d0f');
    content = content.replace(/#1c2230/g, '#111516');
    content = content.replace(/#0B0E11/g, '#060809');
    
    // 特殊列表选中态的处理：将含有 emerald (由indigo转换而来) 的侧栏选中态改为黑色简单渐变
    // bg-[#0a0d0f] border-emerald-500/50 shadow-lg shadow-emerald-500/5 -> bg-gradient-to-r from-white/10 to-transparent border-white/10 shadow-lg shadow-black/20
    content = content.replace(
        /'bg-\[\#0a0d0f\] border-emerald-500\/50 shadow-lg shadow-emerald-500\/5'/g,
        "'bg-gradient-to-r from-white/10 to-transparent border-white/10 shadow-lg shadow-black/20'"
    );

    // 对于选中的模块（也是按钮状），目前是 border-emerald-500/40 shadow-lg shadow-emerald-500/5
    // 这部分需要保持绿色，不用改。

    fs.writeFileSync(file, content);
    console.log(`Updated ${file}`);
} else {
    console.log(`File not found: ${file}`);
}
