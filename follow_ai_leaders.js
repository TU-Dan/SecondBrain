/**
 * X.com / Twitter - 自动关注 TOP 50 AI 领域领袖
 *
 * 使用方法：
 * 1. 在 X.com 上保持登录状态
 * 2. 打开浏览器开发者工具（F12 或 Command+Option+I）
 * 3. 点击 "Console"（控制台）标签
 * 4. 将以下代码全部粘贴进去，回车运行
 * 5. 脚本会自动逐一导航到每个账号主页并点击 Follow
 *    （每次关注之间有 2 秒延迟，避免触发限流）
 */

const AI_LEADERS = [
  // === OpenAI / AGI ===
  'sama',           // Sam Altman - OpenAI CEO
  'gdb',            // Greg Brockman - OpenAI Co-founder
  'ilyasut',        // Ilya Sutskever - OpenAI Co-founder

  // === Google DeepMind / Google ===
  'demishassabis',  // Demis Hassabis - Google DeepMind CEO
  'drfeifei',       // Fei-Fei Li - Stanford AI / Google Cloud AI
  'jeffdean',       // Jeff Dean - Google Senior Fellow

  // === Meta AI ===
  'ylecun',         // Yann LeCun - Meta Chief AI Scientist

  // === Anthropic ===
  'DarioAmodei',    // Dario Amodei - Anthropic CEO

  // === 顶级研究员 ===
  'karpathy',       // Andrej Karpathy - Former OpenAI / Tesla
  'AndrewYNg',      // Andrew Ng - DeepLearning.AI
  'fchollet',       // François Chollet - Keras creator / ARC-AGI
  'goodfellow_ian', // Ian Goodfellow - GAN inventor
  'hardmaru',       // David Ha - Sakana AI CEO
  'mmitchell_ai',   // Margaret Mitchell - AI Ethics
  'emilymbender',   // Emily M. Bender - Linguist / AI critic
  'GaryMarcus',     // Gary Marcus - AI skeptic / researcher
  'tegmark',        // Max Tegmark - MIT / Future of Life
  'random_walker',  // Arvind Narayanan - Princeton CS

  // === AI 产品 / 创业 ===
  'emollick',       // Ethan Mollick - Wharton AI researcher
  'swyx',           // swyx - AI Engineer community
  'karpathy',       // (already above)
  'bentossell',     // Ben Tossell - AI tools curator
  'jxnlco',         // Jason Liu - AI/ML practitioner
  'transitive_bs',  // Lior Sinclair - AI researcher
  'natfriedman',    // Nat Friedman - Former GitHub CEO / AI investor
  'kaifulee',       // Kai-Fu Lee - Sinovation / AI expert

  // === 投资 / 思想领袖 ===
  'naval',          // Naval Ravikant - AngelList
  'pmarca',         // Marc Andreessen - a16z
  'benedictevans',  // Benedict Evans - Tech analyst

  // === AI 安全 / 政策 ===
  'paigebb',        // Paige Bailey - AI researcher
  'mer__edith',     // Meredith Whittaker - Signal / AI ethics
  'timnitGebru',    // Timnit Gebru - DAIR Institute

  // === AI 工具 / 平台 ===
  'huggingface',    // Hugging Face (official)
  'LangChainAI',    // LangChain (official)
  'perplexity_ai',  // Perplexity AI (official)
  'AnthropicAI',    // Anthropic (official)
  'openai',         // OpenAI (official)
  'GoogleDeepMind', // Google DeepMind (official)
  'mistralai',      // Mistral AI (official)
  'xai',            // xAI (official)

  // === AI 媒体 / 观察者 ===
  'nathanbenaich',  // Nathan Benaich - Air Street Capital / State of AI
  'Scobleizer',     // Robert Scoble - Tech evangelist
  'ethanmollick',   // Ethan Mollick (same as emollick)
  'AravSrinivas',   // Aravind Srinivas - Perplexity CEO
  'sama',           // (duplicate, will be skipped)
  'cHHillee',       // Charlie Waite - AI researcher

  // === 中文 AI 圈 ===
  'AndrewYNg',      // (already above)
  'kaifulee',       // (already above)

  // === 补充重要账号 ===
  'elonmusk',       // Elon Musk - xAI / Tesla
  'grok',           // Grok AI (official)
  'StabilityAI',    // Stability AI
  'scale_AI',       // Scale AI
];

// 去重
const uniqueLeaders = [...new Set(AI_LEADERS)];

async function followUser(handle) {
  return new Promise((resolve) => {
    window.location.href = `https://x.com/${handle}`;
    setTimeout(async () => {
      // 找到 Follow 按钮并点击
      const tryClick = (attempts = 0) => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const followBtn = buttons.find(b => b.innerText.trim() === 'Follow' || b.innerText.trim() === '关注');
        if (followBtn) {
          followBtn.click();
          console.log(`✅ 已关注 @${handle}`);
          resolve(true);
        } else if (buttons.find(b => b.innerText.trim() === 'Following' || b.innerText.trim() === 'Unfollow' || b.innerText.trim() === '正在关注')) {
          console.log(`⏭️ 已经关注过 @${handle}，跳过`);
          resolve(false);
        } else if (attempts < 10) {
          setTimeout(() => tryClick(attempts + 1), 500);
        } else {
          console.log(`⚠️ 未找到关注按钮 @${handle}`);
          resolve(false);
        }
      };
      tryClick();
    }, 2500); // 等待页面加载
  });
}

async function followAll() {
  console.log(`🚀 开始关注 ${uniqueLeaders.length} 位 AI 领袖...`);
  let followed = 0;
  let skipped = 0;

  for (let i = 0; i < uniqueLeaders.length; i++) {
    const handle = uniqueLeaders[i];
    console.log(`[${i+1}/${uniqueLeaders.length}] 正在处理 @${handle}...`);
    const result = await followUser(handle);
    if (result) followed++;
    else skipped++;
    await new Promise(r => setTimeout(r, 2000)); // 额外 2 秒间隔
  }

  console.log(`\n🎉 完成！已关注 ${followed} 人，跳过 ${skipped} 人`);
}

// 运行！
followAll();
