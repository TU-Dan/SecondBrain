# An Interview with OpenAI CEO Sam Altman and AWS CEO Matt Garman About Bedrock Managed Agents

**生成时间**: 2026-05-27 14:24

---

对OpenAI CEO山姆·奥特曼和AWS CEO马特·加曼关于Bedrock托管代理的采访

收听本期内容：

早上好，

正如我昨天提到的，今天的Stratechery采访在时间上有所提前——周二而非周四——而在发布上有所延迟——东部时间下午1点而非早上6点——因为话题受到 embargo（禁发令）限制。过去几天，这个禁发令给我带来了一些奇怪的情况：

- 上周五，我进行了以下采访，采访对象是OpenAI CEO山姆·奥特曼和AWS CEO马特·加曼，内容是关于由OpenAI驱动的Bedrock托管代理；自然，我的问题之一是这如何与OpenAI和微软的协议（即Azure独家访问OpenAI模型）相契合。
- 周日深夜，我通过小道消息得知微软将在周一早上宣布某事；我猜想这会不会是一起先发制人的诉讼！
- 周一，微软和OpenAI宣布他们修改了协议，允许OpenAI在其他云提供商（包括AWS）上提供其产品。

所以，我们现在就在这里。

我认为微软-OpenAI的协议对双方都很有意义。以下是微软帖子中新安排的要点：

- 微软仍然是OpenAI的主要云合作伙伴，OpenAI产品将首先在Azure上发布，除非微软无法或选择不支持所需的能力。OpenAI现在可以在任何云提供商上向客户提供其所有产品。
- 微软将继续拥有OpenAI模型和产品的知识产权许可，直至2032年。微软的许可现在将是非排他性的。
- 微软将不再向OpenAI支付收入分成。
- OpenAI向微软的收入分成支付将持续到2030年，独立于OpenAI的技术进展，比例相同但设有总上限。
- 微软继续作为主要股东直接参与OpenAI的增长。

我认为最重要的一点是最后一点。Azure因成为唯一能提供OpenAI模型的大型云服务商而拥有真正的竞争优势，但这同时也阻碍了OpenAI，尤其是当人们清楚许多企业首先关心的是在他们当前选择的云上访问模型时；我一直在指出，这对Anthropic来说是一个真正的竞争优势。换句话说，Azure的排他性正在积极损害微软对OpenAI的投资，而鉴于Anthropic今年的快速增长，微软需要照顾其投资，即使这会削弱Azure的差异化。

与此同时，OpenAI显然将AWS视为一个巨大机遇——以至于他们愿意在未来几年放弃与Azure相关的收入（根据前一点，这将有助于Azure管理层对失去排他性感到更好受；他们的损益表在不向OpenAI支付收入分成的情况下会好看得多）。OpenAI还解除了微软的AGI条款；现在两家公司之间的协议将无论如何运行到2032年。

似乎明确的是，OpenAI 的重点将放在 AWS 上，而在这方面最有力的证据就是本次采访的主题：由 OpenAI 驱动的 Bedrock 托管代理。理解这一产品最简单的方式是将其视为 AWS 中的 Codex；Codex 之所以能运作，很大程度上在于它是本地的，这免费为你带来了大量复杂性，尤其是在安全性方面。而如何让代理在整个组织中运作则完全是另一回事，该产品的目标是为那些已将大部分数据存储在 AWS 中的组织，使这些工作流程更易于访问。

为此，在本次采访中，我们讨论了 AWS 如何创建了整个云类别，及其对初创公司的影响，以及 AI 与之前的范式转变既有相似之处又有不同之处。然后我们讨论了 Bedrock 托管代理，它是什么，以及它与亚马逊现有的 AgentCore 产品有何不同。我们还谈到了 Trainium，以及为什么芯片对大多数 AI 用户来说并不重要，以及为什么与谷歌专注于全面整合相比，合作更有意义。

提醒一下，所有 Stratechery 内容，包括采访，都可以作为播客收听；点击本邮件顶部的链接，将 Stratechery 添加到你的播客播放器中。

进入采访环节：

与 OpenAI 首席执行官 Sam Altman 和 AWS 首席执行官 Matt Garman 关于 Bedrock 托管代理的采访

本次采访为清晰起见进行了轻微编辑。

主题：

AWS 与初创公司 | Bedrock 托管代理 | 本地与云端 | AgentCore 与托管代理 | Trainium | 客户需求 | 构建 AI 堆栈

AWS 与初创公司

Matt Garman 和 Sam Altman —— 嗯，Matt，欢迎来到 Stratechery —— 还有 Sam，欢迎回来 [我之前曾在 2025 年 10 月、2025 年 3 月和 2023 年 2 月采访过 Altman]。

Sam Altman：谢谢。

Matt Garman：谢谢，感谢邀请我。

那么 Matt，这是你第一次上 Stratechery。可惜，我认为 Sam 的在场会妨碍通常的“了解你”环节。再说了，他也不想听我们回忆在凯洛格商学院的时光，但很高兴能有校友一起上播客。

MG：是的，我很高兴来到这里。我下次再来，我们可以做更深入的探讨。

那太好了。你从实习生起就在 AWS 工作，现在在 AI 浪潮中负责整个组织。构建 AI 业务与构建最初的商品计算业务（姑且这么说）有哪些相同之处，又有哪些真正不同之处？

MG：我认为相同之处在于，我看到了同样的兴奋，以及构建者能够做到他们以前从未能做到的事情。其中一个很酷的地方是，当我们刚开始 AWS 时，开发者突然能够获得只有那些拥有数百万美元建造数据中心的大型公司才能使用的基础设施。用一张信用卡和几美元，他们就能启动应用程序，这确实让

爆炸性地拓展了人们在互联网上构建一切的可能性。我们秉持这样一种理念：人们可以随心所欲地构建任何东西，我们不会预先假定他们应该做什么，而世界上的创造力是无限的——如果我们能把强大的工具放在他们面前，他们就会创造出有趣而惊人的事物。

我认为，这对于赋能开发者所能做的事情而言，其变革性即使不更大，也至少同样巨大。当你思考什么是可能的时候，你不需要去学校学习十年编程才能构建一个应用程序，你也不需要拥有数百人的庞大团队以及数月数月的时间去构建东西。你可以用小型团队构建东西，你可以快速构建并快速迭代，而人工智能正在解锁世界各个方面的各种创新。我认为这在很多方面都非常相似，看到它为客户群体带来的赋能，令人无比兴奋。

不过，在AWS出现的时候，有一点是，你是唯一的玩家，所以你几乎免费获得了所有的好处和坏处以及一切。有没有那么一点感觉，在AWS时代，很多是关于商品化计算，使其可互换、弹性化、廉价——而在人工智能领域，尤其是在训练方面，感觉成功的抽象更多是关于这些真正垂直整合的超大规模集群、真正先进的网络，以及软件和硬件之间紧密的联系。这对你来说是否有点意外，你现在面对它时——不再是全新的，“我们是这里唯一的玩家，我们对大规模计算有特定的看法”，至少在人工智能的头几年，这也许并不完全契合？

MG：我不认为这对我们来说有什么不同。我认为不同的地方，只是令人难以置信的快速采用规模，我认为这大概让所有人都感到惊讶。Sam，如果你不同意，你可以提出不同意见，但仅仅是采用的速度以及人们抓住这些能力的速度之快，我认为已经让所有人震惊。

如果你回顾一下，当我们开始云计算时，情况是不同的。我们花了很长时间来解释为什么一个书商能提供你的计算能力，那需要大量的解释来说明什么是云计算。有很多人们遗忘的艰苦工作，但在2006年，这并非理所当然地认为世界上的计算就会这样发展，所以当时有很多艰苦的工作。

你认为你现在是否还需要做一些解释工作，因为很多人还锚定在训练时代，而你说，“我们在考虑推理时代”，那将是不同的东西，也许你仍然需要再次启动那些解释能力？

MG：确实需要，但人们理解你在说什么的速度完全不同了。所以我认为是的，我认为如果你从人们说“那

从“这东西看起来挺酷的，有个能聊天的智能聊天机器人真不错”，到“我其实能在你的企业里干活”，这中间经历了一些认知转变，但从技术发展的速度来看，这个过程也算相当快了。

我们很快会讲到今天要介绍的产品，我保证。但萨姆——从创业生态的角度看，回顾过去，显然AWS是变革性的，它彻底改变了准入门槛，现在任何人都可以起步了。有种子轮，有天使投资人，它把门槛往后推了，你不需要在PPT里画服务器，你可以先开发一个应用，再去拿A轮融资或其他什么。那么，从你的视角看，当时这种模式所催生的东西，与当今世界相比，有什么不同或相同之处？

萨姆：我认为，大规模赋能创业者的平台有四个重要时刻：互联网、云计算、移动互联网，然后是人工智能。其中第一个我成年后经历的是云计算，在YC（创业孵化器）早期——很难夸大这对创业者意味着怎样的改变。以前，创业者要租用托管空间，组装服务器，把东西放进去，这是个极其复杂的事情，你得筹集大量资金。然后突然之间，尽管云计算是在YC启动之后才出现的，我想大概是第二年吧。

我正要问这个——归根结底，它们是不是比你当时意识到的更加紧密相连？

萨姆：当时感觉它们确实紧密相连，感觉YC从一开始就在乘着云计算的浪潮，因为AWS之前就有一些早期的例子。

有了AWS，你不需要投入那么多钱就能让一个创业项目起步，相比以前的情况。

萨姆：这是一个巨大的赋能变革，也是当时YC听起来那么疯狂的部分原因。人们会说：“你不可能用几万美元就资助一个创业公司，这不可能，服务器成本都不止这个数。”所以，这彻底改变了创业者用小额资本能做的事情。

创业者通常能在重大平台转型时获胜，因为你可以用比以往更快的周期和更少的资本做事，这是创业者击败大公司的经典方式。在我职业生涯初期，我亲眼目睹了云计算带来的这种变化，现在看到公司在人工智能上做的事情，感觉方向非常相似，但正如马特所说，速度快得惊人。

有没有一种情况，是现有的大公司采用人工智能的速度比当年采用云计算快得多？

萨姆：这种情况确实更多，但我也指的是创业公司收入增长的速度——我最近在YC演讲，最后我问：“在YC结束时，一家好公司的收入预期是多少？”

”，他们就会说：“嗯，这每个月都在变，可能我们在批次开始和批次结束时会有不同的答案”，而这种情况以前从未发生过。人们在这个新平台上建立规模化业务的速度，是我前所未见的。

马特，你曾是几乎所有初创公司的首选云服务商，这对整个时代来说是一个巨大的优势。如今，是什么让你成为今天的首选云服务商？是因为你考虑到很多人都在基于 OpenAI API 构建，还是你感觉到，“实际上，我们是从一个非常不同的角度进入这个市场的，我们拥有庞大的现有客户群，他们迫切希望获得 AI 功能，而对于山姆所说的这一整个群体，我们的可见度较低”？

MG：我认为有几个方面。一是我们对合作感到非常兴奋，我认为这对许多初创公司来说将非常有意义。但今天，即使你去和初创公司交谈，绝大多数正在扩张的初创公司仍然在 AWS 上扩张，这有很多原因。规模在那里，可用性在那里，安全性在那里，可靠性在那里，其他独立软件供应商的合作伙伴生态系统也在 AWS 上，客户也在 AWS 上。

（笑）每个人都用过 AWS 面板，不管他们愿不愿意，所以他们已经习惯了。

MG：我们帮助他们。我们花大量时间支持初创公司，无论是通过积分，但不仅仅是积分，还有关于如何设置系统、如何考虑市场推广等方面的建议，我认为这些对许多初创公司来说非常受用。我们投入大量时间和精力来确保这一点，因为我们真的认为初创公司是 AWS 的生命线。从一开始就是这样，就像山姆刚才说的那样，但今天依然如此，我每个季度仍然会去硅谷或其他地方，直接与初创公司会面，了解他们在做什么，确保我们构建的东西能对他们有用。所以，如今争夺初创公司注意力的竞争比 20 年前更激烈，这对我们来说仍然和以往一样重要，我们花大量时间来确保满足这些初创公司的需求。

说那些直接基于 OpenAI API（而不是 Azure 版本）构建的人，更有可能在 AWS 上运行常规计算，然后用 OpenAI 处理 AI，这样说公平吗？

MG：我认为这是如今许多初创公司非常常见的模式，绝对如此。

Bedrock 托管代理

那么，这就引出了今天的公告：由 OpenAI 驱动的 Bedrock 托管代理，我想我没说错吧。据我理解，这个卖点不仅仅是 OpenAI 模型在 AWS 上可用——我认为这不允许——而是 OpenAI 的前沿模型被封装在一个 AWS 原生的代理运行时中，包括身份、权限状态、日志记录、治理和部署。山姆，这样说对吗？

SA: 是的，那相当不错。
谢谢。这是什么？现在用英语解释一下。
SA: 我认为人工智能的下一个阶段，将从你向智能体提供一些文本并得到更多文本作为回报，甚至是你提供一堆代码并得到更多代码作为回报，转变为我们将让这些智能体在公司内部运行，从事各种不同类型的工作。
虚拟同事是我听过的描述方式中相对不那么糟糕的一种，但还没有人完全找到合适的语言来描述它，我们正在打包一个共同开发的新产品，以帮助那些希望构建这类有状态智能体并将其投入使用的公司。再次强调，我认为我们并不确切知道世界将如何谈论和使用这些，但如果你看看 [Codex] 正在发生的事情，我认为这是一个很好的例子，可以让我们看到这一切的发展方向。
工具链、模型运行环境、工具、状态——对你来说，这是一个非常重要的词——内存、权限、评估，对于让智能体真正发挥作用有多重要？
SA: 再怎么强调其关键性也不为过。我不再认为工具链和模型是完全可分离的东西，就像我使用这些工具的经验一样，我非常清楚，当我在 Codex 中触发某个操作并得到惊人结果时，我并不总是知道功劳该归谁——
是模型出色还是工具链出色？
SA: 是的，没错。
工具链在多大程度上是与模型一起开发的？这种集成发生在哪里？是在后训练阶段？还是在提示词中？是什么让这种集成发挥作用？
SA: 两者都有。这实际上不是预训练过程的一部分，但我想说你可以这样看——这里有一个更有趣的事情，那就是我们过去多次看到过这样的例子，那些我们认为非常可分离的东西，逐渐被越来越深入地融合在一起。就像我们最初考虑工具调用的方式，现在已成为使用这些模型的关键部分，但当时我们并没有考虑将其深度集成到训练过程中，而随着时间的推移，我们在这方面做得越来越多。
我还推测，模型和工具链会随着时间推移越来越紧密地结合，而且就此而言，我预计预训练和后训练最终也会随着时间推移越来越紧密地结合。这么说很老套，但我还是要说，因为我认为这非常非常真实——我们在这个范式中还处于非常早期的阶段，这仍然像家用电脑俱乐部时代一样，这个行业远未真正成熟。
这就是为什么我认为这如此有趣，几周前我写过相关文章，在任何价值链中，最终都会出现一个集成点，这个点至关重要，这两个部分必须结合在一起才能发挥作用。而随着时间的推移，这显然也是大量价值汇聚的地方——我的论点就是，这种工具链-模型集成是关键点。这符合你的利益，但听起来你同意这一点。

SA：我同意这符合我的利益，但我也更广泛地说，你在乎的是你输入Codex你想实现什么，然后它就能实现。
你并不关心实现细节。
SA：我认为你并不关心。在我们摸索这一切的过程中，有很多例子表明，我们曾经必须在系统提示层面做某些事，后来却不必做了。这里的一般观察是，随着模型变得更智能，你就有更大的灵活性让它们按你想要的方式行事，这听起来像是一句显而易见的话，但事实确实如此——
告诉一个10岁的孩子该做什么，比告诉一个5岁的孩子更容易。
SA：回想在GPT-3时代，我们为了从这些模型中榨取哪怕一丁点效用而不得不做的事情，现在你永远不必做了，因为模型当然能直接理解并出色地完成任务，而且这一趋势可能会持续得更远。
MG：我正要补充这一点——我完全同意，而且我认为，当你与那些确切知道自己想让这些系统做什么的客户交谈时，在我们进行这种联合协作之前，客户实际上是不得不自己拼凑出解决方案的，对吧？他们希望这些模型和代理能记住彼此良好协作，并希望将它们集成到现有系统中，这不仅仅是第三方工具，还包括他们自己的工具。他们希望模型能学习他们的数据、应用程序和操作环境，而所有这类集成，至少在今天，是留给每个客户自己去完成的。
因此，我们共同推进的这项联合协作的一部分，就是共同构建一种新型产品，真正将这些要素更紧密地结合在一起，这样客户就能更轻松地实现他们想做的事情，其中身份验证已内置在产品中，对数据库进行身份验证的能力全部发生在你的AWS VPC（虚拟私有云）内。如果我们在OpenAI API和AWS这边各自为政，也能实现很多事情，但通过共同构建这个产品，我们让客户能更轻松、更快速地获得价值，并在企业环境中完成他们想做的事情。
那么，你认为在一个通用框架中构建一个功能型代理，只是难度更大？还是说你在降低难度？或者，如果它们没有紧密耦合，有些事可能根本做不了？
SA：回到你之前的类比，在AWS时代之前，如果你愿意站在笼子里买一堆服务器，想办法连接它们，并雇佣自己的网络工程师，你也能做很多事情，然后突然之间，只要你登录AWS控制面板点击“我需要另一个S3实例”之类的，你就能做更多事情，因为激活能量，即基础工作所需的工作量，大大降低了，所以你今天可以用模型做很多事情。

然而，每当我看到有人使用我们的模型，或尝试搭建马特所说的这类工作时，我总在两种情绪间挣扎：一方面高兴于他们如此印象深刻，觉得这是神奇的技术；另一方面又因他们为了让任何东西能运行而经历的痛苦和折磨而抓狂——这不仅仅适用于构建这些产品的开发者，就连使用ChatGPT时，看到人们从这儿复制粘贴到那儿，试图搞出一套复杂的提示词——我知道这种情况会消失，我对此感到兴奋。现在仍然太早，也太糟糕。
只是别取消你与BBEdit的集成，这是我唯一的要求，也是ChatGPT应用中我最喜欢的功能。
萨姆·奥特曼：好的。
（笑）谢谢。
萨姆·奥特曼：A) 这些东西实在太难搞了，我们认为如果能让它变得简单得多，就能为开发者和企业带来更多价值；但B) 有很多事情你根本无法可靠地让它运行起来，我认为通过我们的合作，这不仅会是一个关于易用性、不必自己搭建托管机房之类的故事，我们还将共同探索出许多新东西，让人们能够构建出即使经历大量痛苦和折磨也无法实现的产品和服务。
本地 vs. 云端
我其实想回到关于要构建的东西那个话题上。但先快速回到Codex——Codex是一个工具集和模型，它在本地运行。为什么现在让智能体在本地运行更容易？
萨姆·奥特曼：实际上，我们一开始是在云端运行的，我认为最终你确实希望它在云端运行。
当然。我正在经历向这个云端产品的过渡。但为什么你又回到了本地？
萨姆·奥特曼：你的整个环境都在那里，你的电脑已经设置好，你的数据也在那里，你不需要考虑——它只是更容易运行起来，尽管这不是最终状态。但走向一个智能体在云端运行的世界，当你——如果你有非常繁重的任务，或者需要关闭电脑之类的，你可以把工作交给云端处理，我认为这显然会很棒。但我们在短期内能够提供的易用性，让使用本地环境胜出了。
我想到一种理解方式：你有旧式的安全模型，就像护城河城堡那种东西，而你正在转向一种新的安全模型，即零信任，一切都有适当的权限结构、认证以及所有那些细节。在我看来，将本地运行理解为一种自我强加的护城河城堡——一切都在那里，我假设一切都很好、很容易。而我对这个问题的思考方式，马特，看看你是否认同，就是让所有这些部分在生产环境中实际运行，你甚至不能全部放在本地，你必须从一开始就在这种环境下操作，这样想对吗？

MG：我不认为有任何计算环境真正消除了客户端，本地操作自有其优势。你的iPhone上大多数应用都包含本地组件，无论出于连接性、延迟、本地计算还是文件与应用访问的考虑，这都有其道理。本地客户端确实有独特之处——正如Sam所说，它简单易用、运行良好，但同时也存在局限。
你无法扩展本地笔记本电脑的规模，你拥有的就是这些；一旦进入企业合同环境，两人之间的共享就会变得困难——权限管理、安全边界设定都会更复杂。因此，在这些方面，我认为不能说本地环境是坏事，它只是不同的事物，而最终你会希望在这两者之间架起桥梁。
这正是我的疑问，因为在云时代，你有容器来帮助融合本地与生产环境，但在这个场景下，如果你要处理智能体——就像你说的，假设我是一个虚拟同事或类似存在——如果它们有自己的身份、权限等一切要素，那么即便要构建它们，你也需要在即将部署它们的正确环境中进行，在我看来是这样。
SA：我认为这里有很多问题需要厘清。举个简单的例子：如果你是一家公司的员工，当你使用某项服务时，你希望拥有一个账户，那么你的智能体应该使用你的账户，还是应该使用不同的账户，以便服务器能区分两者？
或者如果你想要多个智能体呢？
SA：正是如此。我猜想我们真正需要的是一种尚未明确的东西——也许当Ben的智能体以Ben的身份登录时，它使用Ben的账户，但会注明自己是智能体而非真正的Ben。我们甚至还没有思考这种原语，但可能很快需要解决这个问题。我的感觉是，随着智能体加入劳动力队伍并以越来越高的自主性和任务复杂度运作，还会有50个类似的问题出现——我们关于软件如何工作、企业内部或更广泛的互联网上访问控制和权限如何运作的许多心智模型，都将不得不进化。
Matt，在智能体的安全策略和访问策略方面，你怎么看？
MG：是的，我认为这正是当我们将更多工作负载迁移到云端时，可以作为一个中央组织对某些安全环节拥有更多控制权的地方。而且，当我们与客户交流时，这确实是他们担心的核心问题：“我喜欢这些强大模型和智能体所能带来的承诺，但如何确保我不会因操作失误而引发公司级别的灾难？”

”，而且外界也存在这种担忧。

我认为我们可以在这方面提供帮助，因为这些都是可以解决的问题，确实如此。而且，我认为，给一些客户信心，“嗯，它在VPC内部运行”，这样你至少可以控制那个边界，并知道它能访问什么；或者它通过这个网关，你可以给它权限，就像你在环境其他部分给它一个角色一样。这些是我们在过去20年里构建起来的非常丰富的功能集，因此不仅仅是Y Combinator的初创公司，全球的银行、医疗机构、世界各地的政府机构都能使用AWS，并且围绕它建立了所有这些安全架构，我认为这可以进一步加速他们利用这项技术，并借助这些保障措施快速推进。

我认为很多时候，当你身处一家公司，尤其是那些规避风险环境中的公司时，拥有这些安全护栏，让他们说：“如果它在沙盒内运行，我就很乐意快速推进”，这实际上可以帮助我们的许多客户开始将这项技术用于更广泛的场景。

**AgentCore 与托管代理**

你提到的许多在过去20年里开发并试图为代理部署的能力，如今都通过AgentCore展现出来。那么，由OpenAI驱动的Bedrock托管代理与Bedrock AgentCore之间是什么关系？

MG：我们共同构建的很多东西都建立在AgentCore的基础模块之上，以便将其中一些部分整合在一起。

所以，这就像是一个位于其上的超集？

MG：AWS团队和OpenAI团队一起使用了AgentCore组件、OpenAI模型以及许多其他部分，共同构建了这个产品。

AgentCore是我们的一套原语，就像在AWS中一样，如果你想构建自己的代理工作流，你可以做到。你可以拥有一个记忆组件、一个安全执行环境、一个权限管理能力，然后你可以去配置所有这些。如今，我们有客户在生产环境中运行这些，并且正在做非常酷的事情。

但不是与OpenAI一起。

MG：但不是与OpenAI一起，他们目前必须使用不同的模型，这倒是真的。实际上，这不完全正确，我们有用户正在用OpenAI做这件事。

哦，只是调用另一个云或其他什么。

MG：他们直接调用OpenAI模型。所以，实际上我们绝对有用户现在就在用OpenAI做这件事，只不过不是在Bedrock内部原生进行，但他们仍然在使用它。这是一个开放的生态系统，你可以利用不同的能力去构建任何你想要的东西，我打赌人们会继续这样做。我们有喜欢构建的开发者，用Sam的类比来说，他们今天仍然喜欢在家里自己组装电脑，即使你其实不必这么做，而且尽管人们喜欢构建，我们认为人们也会继续这样做。

很长一段时间内，他们都会自行构建自己的智能体，但绝大多数用户希望有一种更简单的方式，不必亲自配置所有这些组件，而这正是我们此次合作中推出的部分内容。  
说得更清楚些，你提到Bedrock托管智能体提供的托管体验，你也可以使用AgentCore并从某个模型（无论是在AWS上还是其他地方）获取能力。萨姆，我想明确一下，这个问题是问你的：OpenAI在Azure上提供的服务，只是让你直接访问API，这与亚马逊上的托管服务是不同的，对吗？  
SA：对，没错。  
你对此很有信心，认为在所有条款中这种界定都是恰当的，未来不会出现问题？  
SA：是的，我认为事情会随着时间推移而演变，但作为起步方式，我对此很有信心。  
这会是AWS的独家服务吗？还是你预计会在其他云平台上提供这种托管智能体服务？  
SA：是的，我们与亚马逊独家合作，对此我们感到兴奋。  
这种独家性有多大程度是“看，我们使用了亚马逊的所有API，当然只能在亚马逊上运行”，还是说这整体上是一种托管体验的概念，而不仅仅是“我们使用亚马逊API”，而是“目前这将在亚马逊上运行”？  
SA：从精神层面来说，我们希望这是两家公司之间的联合努力。  
明白了。新闻稿确实提到了一些内容，这又回到了马特你之前提到的观点：你可以调用其他API并自行将所有部分拼接起来。在这种情况下，客户数据保留在AWS内部，那么OpenAI具体能看到什么？这意味着什么？  
MG：没错。所以整个过程都保留在你的VPC内，数据在Bedrock环境中受到保护。  
明白了。这将通过Bedrock在OpenAI模型上运行，这些模型会运行在Trainium上吗？  
MG：它们会通过不同计算资源的混合——部分在Trainium上，部分在GPU上。  
这只是时间安排的问题吗？因为我认为作为你们几个月前公告的一部分——  
MG：部分原因是时间和能力问题，我认为我们会混合使用构建系统的不同组件，为不同部分选择合适的基础设施。但随着时间的推移，越来越多的部分将运行在Trainium上。  
SA：我们非常期待让这些模型在Trainium上运行。  
Trainium  
马特，一个快速问题，只是关于Trainium的一般性问题。Trainium，这样理解是否合理——这也是我目前的思考方式，所以我想确认是否正确。Trainium——这个名字很不幸，因为它未来实际上将主要用于推理——其首要表现形式是通过像Bedrock这样的托管服务，客户甚至不一定知道自己使用的是哪种计算资源，这样理解对吗？  
MG：首先，我为所有AWS服务的糟糕命名承担责任。

听着，我有个叫 Stratechery 的口碑网站，所以我对糟糕的命名深有同感。  
SA：我觉得 Trainium 是个很酷的词。  
MG：确实是个很酷的词。  
它是个很酷的词，但感觉它更像推理芯片，而不是训练芯片。  
MG：是的。不过，抛开命名不谈，它对训练和推理都有用。而且，这是一款我们非常兴奋的芯片，无论是当前几代还是未来迭代，我们都认为它会成为一项巨大的业务，并真正推动我们共同完成的许多事情。  
顺便说一句，我认为通过抽象层，你将与许多这类加速芯片交互。所以绝大多数客户也不直接与 GPU 交互，除非是在笔记本电脑之类设备上处理图形。但当你与 OpenAI 对话时，即使它们运行在 GPU 上，你也不是在与 GPU 对话；如果你与 Claude 对话，你是通过 GPU、Trainium 或 TPU 进行，但你并不与这些芯片直接交互，你交互的是接口。而目前绝大多数推理工作都在少数几个模型上完成。  
因此，无论是 5 个、10 个、20 个还是 100 个，都不是数百万人在直接对这些芯片编程，未来也会如此，因为这些系统非常复杂且庞大。如果你要去训练一个模型，没有多少人拥有足够的资金，也没有多少人具备实际管理的专业知识。这些是非常复杂的系统，OpenAI 团队在从大型计算集群中榨取价值方面能力惊人。但无论芯片是什么，没有多少团队能做到这一点，所以我认为，对所有加速芯片来说，这都将是事实。  
SA：Ben，我越来越觉得我们公司要做的事就是成为一家“代币工厂”。但客户关心的是，我们能以最低价格提供最好的智能单位，并且他们想要多少就有多少，想要多大容量就有多大容量。  
你认为我们是否应该坚持按代币定价？从长远来看，这合理吗？  
SA：不。事实上，我们刚推出的 5.5 模型就有一个有趣的例子：它的每代币成本远高于 5.4，但获得相同答案所需的代币数量却大幅减少，而客户实际上并不关心答案用了多少代币，他们只想要完成工作，并再次获得一个价格和相应的容量。  
所以，也许我说“代币工厂”是错的，但我们更像是“智能工厂”之类的东西。我们只想以最低价格提供尽可能多的智能单位，无论是更大的模型用更少代币，还是更小的模型用更多代币，无论是 GPU、Trainium 还是其他芯片，无论我们还能在这方面创造性地做哪些其他事情，我认为客户都不在乎。

事实上，他们并不真正与之交互。当你把某样东西放入 Codex，或者你在 SRE（有状态运行时环境）中构建一种新的代理时，你根本不必考虑这一点，而应该惊叹于以如此低的成本获得了如此多的收益。

减少的 token 使用量是模型层面的，还是框架层面的？
SA：主要是模型层面的，框架层面也有一点。
明白了。顺便问一下，马特，我问过山姆一个独家问题——你是否有计划为其他模型提供类似的托管服务？
MG：我们目前专注于与 OpenAI 合作开展这项工作。我们对正在共同推进的事情感到非常兴奋，而“时间的圆满”是一个漫长的过程。
“时间的圆满”是一个漫长的过程，我就让你保留这个说法了。没关系，我不得不问这个问题。

客户需求
关于客户，我确实有一个问题，山姆，也听听你的看法——我很好奇：当人们实际投入生产时，OpenAI 的责任在哪里结束，AWS 的责任又从哪里开始？在我看来，如果所有数据都在 AWS 上并保留在那里，并且他们在更高层次上运营，这最终是 AWS 的责任吗？从消费者的角度来看，我这样理解对吗？
MG：是的，我认为没错。当你需要寻求帮助时，你会联系 AWS 支持，这是你 AWS 环境的一部分，你与它一起构建，你的 AWS 账户代表会在那里帮助你。在构建过程中，我们也会邀请我们的 OpenAI 同事来帮助你弄清楚如何最好地利用这一点或其他方面。如果遇到需要他们帮助解决的 bug，我们会升级给他们，但 AWS 将是你主要接触的前线支持。

山姆，相对于你的核心 API 业务，你如何看待这项业务的规模？
SA：我希望它会非常庞大，我们为此投入了大量精力，我们承诺购买大量计算资源，我相信会有大量收入来支持这一点。我逐渐形成的框架是，在足够低的价格下，对智能的需求基本上是无限的。
那么在这方面它是非常有弹性的吗？你降低价格，需求就会上升？
SA：当然是这样，但同样，你可以降低水的价格，也许你会多喝一点水，也许你会一天洗两次澡而不是一次，这里面有一些弹性，但到了某个点你会想，“你知道吗，我有足够的水了”。
而且，如果你必须用水，无论价格多高你都会买。
SA：其他公用事业也是如此，如果电更便宜，你肯定会多用一些，但如果你把智能视为一种公用事业，我不知道还有哪种公用事业会让我觉得：“我只想要更多，只要价格足够低，我就会多用。”
MG：我实际上要说，有趣的是，这在很大程度上也适用于计算能力——如果你想想今天一个计算周期的成本与 30 年前相比，我不知道便宜了多少个数量级，而今天销售的计算资源比以往任何时候都多。

没错。人们通常不会真正考虑计算成本，除非达到极高量级、成本成为实质性因素时才会在意；但从战略层面看，普遍默认你拥有计算资源。那么，AI发展到何种阶段才能让“我在这上面花了多少钱”不再是首要思考的问题？

SA：我认为这并非首要思考。目前，要求我们“不管价格多少，请给我更多算力，我只需要更大容量，愿意额外付费”的客户，远多于跟我们讨价还价的客户。

但我确实认为，我们将继续大幅降低价格——或许我们越降价，涌入的财富量反而会越来越多。不过我有信心，我们将持续显著降低当前智能水平的成本——有一点让我有些意外的是，目前总市场需求中有多大比例集中在最前沿领域（我不确定这种情况是否会持续）。

对，这方面存在很多疑问。服务前沿领域成本极高，人们本可以选择上一代技术，但你的意思是，无论成本如何，人们都只想留在前沿？

SA：目前来看确实如此。

MG：我认为这是个好信号，说明我们离理想状态还差得很远，需求远未饱和。我真心觉得，就像40年前的计算需求——当时计算机贵得离谱，而现在每个人手机里的算力都远超当年，我们卖出了数十亿台这样的设备。我相信AI世界也会如此：如今大家都在追求前沿模型，因为要完成大量有用工作就必须用它，人们对这些能力充满兴奋。

我认为未来会形成多种模型并存的格局——有些小型模型甚至能完成最新OpenAI模型还做不到的事，但它们会更小、更便宜、更快；而超级大模型则致力于攻克癌症等难题。但我认为，我们仍处于可能性实现的早期阶段，当你在早期阶段看到如此巨大的需求和增长时，未来前景令人振奋。

这里是否存在一种冷眼旁观的观点：山姆，你有一批客户说“我们很想用OpenAI模型，但所有数据都在AWS上，我们不会迁移”；而马特，你则说“看，我们所有东西都在AWS上，你能去获取OpenAI模型吗？”——这只是在满足这种需求。而由于AWS是最大的平台，这种需求规模惊人。这仅仅是最简单的答案吗？还是说，你们确实认为能提供高度差异化的服务，从而为彼此吸引新客户？

SA: 我们显然非常激动能够接触到 AWS 的客户，而且有这么多人喜爱 AWS。是的，这是事实。
MG: 这部分确实是真的。
（笑）没错。
MG: 反过来，我们的客户也非常兴奋能够接触到 OpenAI 的技术。
SA: 但我确实认为，我们有机会共同构建一些令人难以置信的新事物，而且我希望当人们在一年后回顾这一点时，他们谈论的最重要的事情不是“哦，终于可以通过 AWS 访问这些模型了”之类的，而是“哇，我们当时没意识到这个新产品有多重要”。我认为，在模型、工具和能力层面，我们正接近一种全新的计算方式，这将与人们过去思考的“我需要一个API来调用这个模型”等现有方式截然不同。
MG: 我完全同意，正是如此。第一部分很好也很棒，而第二部分，我认为，才是让我们所有人都感到超级兴奋的地方。
构建AI堆栈
关于这一点，我提到过我想回到之前的话题，但我有一个理论，可能对也可能不对，我很好奇你们对此的看法，关于需要构建的东西。具体来说，最终可能会存在一个真正的中间件或中间层，其中包含组织中所有不同的数据库、SaaS应用以及各种零散的数据，这些数据可以跨越不同事物，你有一个代理层/工具层，或者我猜是工具层，位于顶层之上，中间有东西需要构建，而OpenAI Frontier对此有所涉及。这是其中的一部分吗？还是这是需要构建的东西？或者我完全搞错了，我们根本不需要这个？
SA: 你说得完全正确，我们确实需要一些东西在那里。最近我与客户交谈时，比如大型企业，他们说：“我想要某种代理运行时环境，我想要一个管理层，可以连接我的数据到代理，同时确保我了解代币的消耗情况，并有一些监督，我还想要某种工作空间”——希望会是Codex——“类似的东西给我的员工”，人们所要求的这个组合正变得异常一致，但还有工作要做，现在要去构建所有这些产品。
感觉似乎需要一个几乎双重的代理层。有一个代理层来维护中间层，这个中间层不断深入探索所有这些数据源，然后还有一个实际的用户界面层，人们在那里进行交互。这符合我们未来的方向吗？还是说这不对？
SA: 关于这两点，我同意这是当今世界的一个图景。随着模型变得非常智能，我认为我们并不确切知道未来的架构会是什么样子。
现在，人们在这个所谓的用户代理层，确实希望与多个代理交互，并且

我们让它能够为各种事务构建智能体，它们可以相互对话，做其他事情，然后在公司管理层，人们拥有所有这些控制手段，来帮助AI在文件系统中探索和查找文件。

到了某个时刻，你会意识到你只是在毫无理由地固守过去，这本来就应该直接内置在模型中。

萨姆·奥尔特曼：这正是我想说的。到了某个时候，你可能会说，“实际上，我们拥有如此不可思议的能力，让我们重新架构整个系统吧。”

马特·加曼：是的，我同意。而且我认为有些不同之处，我不确定我们是否都清楚那是什么，但这正是美妙之处的一部分——你让客户使用和构建，你可以从他们那里学习，并弄清楚如何让这变得更容易、更快、更好，为他们服务。

萨姆，这是我们第二次做这种产品发布访谈，上一次是和凯文·斯科特以及新版必应——当时你对自己对谷歌构成的威胁相当自信，你觉得结果如何？

萨姆·奥尔特曼：我认为我们做得比我预期的要好。ChatGPT，我认为，是自Facebook以来第一个真正大规模的新消费产品。

这真的是答案吗？你做得比预期好，但这主要体现在ChatGPT上，而不是其他领域？

萨姆·奥尔特曼：不，我认为我们在API方面也做得相当好，特别是在Codex上，但那不是我当时所想的。当时，我在想也许这些新型语言界面会改变人们在互联网上查找信息的方式，而且你知道——谷歌，也是一家绝对杰出的公司，我认为从他们所做事情的广度和深度来看，谷歌在很多方面仍然被低估了，但我对ChatGPT的相对表现感到满意。

实际上，我也有一个关于谷歌的问题要问你，马特，类似的情况。谷歌本周刚刚发布了消息，托马斯·库里安在谈论他们完全集成的技术栈，从模型到芯片再到智能体层，从上到下所有这些东西。你现在和另一位公司高管在一起，从定义上讲，在亚马逊内部并非完全集成，但有没有一点是，之前大家都批评你没有前沿模型——现在我们已经进入这种推理领域，你习惯于为很多公司提供服务。你是否因为保持中立而最终处于一个更好的位置？这是有意为之，还是你无意中进入了一个你没想到会这么好的位置？

马特·加曼：有一点是有意的。自从我们创办AWS以来，我们一直将合作伙伴视为支持最终客户的关键部分。从一开始，我们的战略中一个极其重要的部分就是与合作伙伴紧密合作，也许与其他公司不同，我们认为如果合作伙伴成功，他们在我们之上或与我们共同构建，如果他们成功，那么我们就成功，这很棒。

我们视之为……

共同把蛋糕做大，那就是双赢，但并非所有人都这样看待世界。有时他们会说“我必须拥有一切”，这也没关系，这是人们持有的一种观点。但我认为选择很重要，这样最好的产品才能胜出。顺便说一句，在那个世界里，你可以拥有第一方产品，也可以拥有大量第三方产品，但我们的观点是希望客户能够选择最适合他们的东西。如果最适合的是你自己构建的产品，那太棒了。

对我们来说，如果最适合的是合作伙伴构建的产品，但它是基于我们的平台，我们也视之为胜利，因为这对客户来说是最好的。我们一直这样认为，实际上这也是我们在AI领域构建Bedrock平台的方式。我们希望支持广泛的模型，支持广泛的能力，事实确实如此，从数据库到计算平台再到其他类似领域，一直如此。

所以我认为这是一项有意的战略，也是一项客户欣赏的战略，因为他们喜欢这样，我们也很高兴能继续深入贯彻这一战略。

是的，这很有趣。软件、平台、基础设施之间存在平衡，每个人都声称会服务所有人。但感觉上，回顾AWS起步时，你们是从I（基础设施）开始的，这给了你们几乎最大的灵活性，在我看来，这能让你们与Sam在中间地带相遇。Sam有出色的S（软件），你们一起构建P（平台），我想可以这样表述。

MG：没错。这确实会带来困难，比如你说“我们只有一个S3”，没有其他S3产品，这部分确实如此。所以一些核心组件，如你所说，在基础设施层，我们确实非常依赖自己构建的东西。但随着你向上移动堆栈，我认为会有更广泛的能力集，如果你这样看待世界——我不认为有任何一家公司能拥有所有应用程序，而且随着你向下深入堆栈，到达模型和服务层时，数量会减少，再往下到基础设施层，数量更少，我们的观点是拥抱整个合作伙伴群体对我们的最终客户来说是极好的。

Sam，最后还有什么想说的吗？

SA：我认为说得非常好。我确实认为开发者现在能够构建的新一代产品潜力巨大，考虑到我们预计未来一年模型能力的进步速度将非常显著，我们能够一起踏上这段旅程，并真正尝试构建一个平台来实现它，时机正好，我认为人们会喜欢的。

非常好。Matt，Sam，感谢你们来到Stratechery。

MG：太棒了。感谢邀请我们。

SA：谢谢。

本期《每日更新访谈》也提供播客版本。如需在播客播放器中收听，请访问Stratechery。

《每日更新》仅供单个收件人使用，但偶尔转发完全没问题！如果您希望为团队订购多份订阅并享受团体折扣（最少5份），请直接联系我。
感谢您作为支持者，祝您度过愉快的一天！

---

An Interview with OpenAI CEO Sam Altman and AWS CEO Matt Garman About Bedrock Managed Agents

Listen to this post:
Good morning,
As I noted yesterday, today’s Stratechery Interview is early in terms of my timing — Tuesday instead of Thursday — and late in terms of delivery — 1pm Eastern instead of 6am — because the topic was embargoed. That embargo created a bit of a weird situation for me over the last several days:
- Last Friday I conducted the following interview with OpenAI CEO Sam Altman and AWS CEO Matt Garman about Bedrock Managed Agents, powered by OpenAI; naturally, one of my questions was about how this fit in with OpenAI’s deal with Microsoft giving Azure exclusive access to OpenAI models.
- Late Sunday I heard through the grapevine that Microsoft would announce something Monday morning; I wondered if it might be a preemptive lawsuit!
- On Monday Microsoft and OpenAI announced they had amended their agreement, allowing OpenAI to serve its products on other cloud providers, including AWS.
So here we are.
I think the Microsoft-OpenAI deal makes a lot of sense for both sides. Here are the bullet points of the new arrangement from Microsoft’s post:
- Microsoft remains OpenAI’s primary cloud partner, and OpenAI products will ship first on Azure, unless Microsoft cannot and chooses not to support the necessary capabilities. OpenAI can now serve all its products to customers across any cloud provider.
- Microsoft will continue to have a license to OpenAI IP for models and products through 2032. Microsoft’s license will now be non-exclusive.
- Microsoft will no longer pay a revenue share to OpenAI.
- Revenue share payments from OpenAI to Microsoft continue through 2030, independent of OpenAI’s technology progress, at the same percentage but subject to a total cap.
- Microsoft continues to participate directly in OpenAI’s growth as a major shareholder.
I think the most important point is the last one. Azure had a real competitive advantage thanks to being the only hyperscaler able to offer OpenAI models, but this also hindered OpenAI, particularly once it became clear that many enterprises cared first and foremost about accessing models on their current cloud of choice; I’ve been noting for a while that this was a real competitive advantage for Anthropic. In other words, Azure’s exclusivity was actively damaging Microsoft’s investment in OpenAI, and given Anthropic’s rapid growth this year, Microsoft needed to tend to their investment, even if it diminished Azure’s differentiation.
OpenAI, meanwhile, clearly sees AWS as a massive opportunity — so much so that they are forgoing Azure-related revenue for the next few years (which, per the previous point, will help Azure management feel better about losing their exclusivity; their PnL is going to look a lot better without paying a revenue share to OpenAI). OpenAI is also releasing Microsoft from the AGI clause; now the agreement between the two companies will run through 2032 no matter what.
What does seem clear is that OpenAI’s focus is going to be on AWS, and the greatest evidence in that regard is the topic of this interview: Bedrock Managed Agents, powered by OpenAI. The easiest way to think about this offering is Codex in AWS; a lot of what makes Codex work is the fact that it is local, which gives you a lot of complexity, particularly in terms of security, for free. It’s another thing entirely to figure out how to make agents work across an organization, and the goal of this offering is to make these workflows much more accessible for organizations who already have most of their data in AWS.
To that end, in this interview, we discuss how AWS created the entire cloud category, and the impact it had on startups, and how AI is both similar and different to that previous paradigm shift. Then we discuss Bedrock Managed Agents, what it is, and how it differs from Amazon’s existing AgentCore offering. We also touch on Trainium and why chips won’t matter to most AI users, and why partnering makes sense relative to Google’s focus on full integration.
As a reminder, all Stratechery content, including interviews, is available as a podcast; click the link at the top of this email to add Stratechery to your podcast player.
On to the Interview:
An Interview with OpenAI CEO Sam Altman and AWS CEO Matt Garman About Bedrock Managed Agents
This interview is lightly edited for clarity.
Topics:
AWS and Startups | Bedrock Managed Agents | Local vs. Cloud | AgentCore vs. Managed Agents | Trainium | Customer Demand | Building the AI StackAWS and Startups
Matt Garman and Sam Altman — well Matt, welcome to Stratechery — and Sam, welcome back [I previously interviewed Altman in October 2025, March 2025, and February 2023].
Sam Altman: Thank you.
Matt Garman: Thank you, thanks for having me.
So Matt, this is your first time on Stratechery. Alas, I think that Sam’s presence is going to preclude the usual getting to know you section. Besides, he doesn’t want to hear us reminisce about our times at Kellogg Business School, but it is good to have a fellow alumnus on the podcast.
MG: Yeah, I’m happy to be here. I’ll come back another time and we can do a little deeper dive.
That’d be great. You’ve been working on AWS since you were an intern, and you’re now in charge of the entire organization during this AI wave. What aspects of building the AI business are the same as building the original commodity compute business, for lack of a better term, and what aspects are really different?
MG: I think that the parts that are the same are that I see that same excitement and builders out there being able to do things that they were never able to do before, and one of the cool things is when we first started AWS, is developers all of a sudden could get their hands on infrastructure that was only available to the largest companies who had millions of dollars to go build data centers. With a credit card and a couple of dollars, they could spin up applications and it really exploded what was possible for people building out there on the Internet. We kind of took the idea that people could build whatever they want and we weren’t going to presuppose what they should do and that the creativity of the world out there was, if we could put powerful tools in front of them, they’d build interesting and amazing things.
I think this is as much, if not more, transformational to what it’s enabling builders out there to do. As you think about what’s possible, you don’t have to have gone to school and learned for 10 years to code in order to go build an application, you don’t have to have huge teams of hundreds of people and months and months and months of time to go build things. You can build things with small teams, you can build it fast and you can iterate quickly, and AI is unlocking all sorts of innovation across every different aspect of the world. I think in many ways that’s very similar, and it’s super exciting to see what it’s enabling from the customer base out there.
There was a bit, though, when AWS came along, you were the only one, so you get all the upsides and downsides and everything sort of for free. Is there a bit where it felt like in the AWS era, there’s a lot about commodity compute, making it fungible, elastic, cheap — in AI, particularly in training, it feels like the winning abstraction was more about these really vertically integrated super clusters, really advanced networking, and really tight linkages between software and hardware. Was that sort of a surprise for you, where you’re coming at it now — instead of fresh, “We’re the only ones here, we had a particular way of looking at large-scale compute”, and at least for the first few years of AI, it maybe didn’t perfectly align?
MG: I don’t know that it was different for us. I think for what was different though, is just the incredible rapid scale of adoption, and I think that that’s probably surprised everybody. Sam, you can weigh in different if you disagree, but just the speed of adoption and how fast people have grabbed onto the capabilities there, I think has surprised everyone.
It’s different if you go to the, when we started cloud computing, it took us a really long time to explain why a bookseller would provide your compute power, that was a lot of explanation to explain what cloud computing was. There was a lot of hard work that people forget, but back in 2006, it wasn’t a given that that’s just how the world’s computing would move to and so there was a lot of kind of hard work there.
Do you think you had to do a bit of explaining now though, because lots of people were anchoring on the training era and you’re like, “We’re thinking about the inference era“, and that’s going to be something different, maybe you still had to get those explanatory powers going again?
MG: You do, but it’s just how quickly people understand what you’re talking about is just totally different. So I think yes, I think if you move from where people are saying, “That does seem kind of cool, and it’s really neat that I have this intelligent chatbot that I can talk to”, going to, “I can actually do work in your enterprise”, has been a little bit of an education, but it’s also been relatively quick in the scope of how fast technology moves.
We’re going to get to the product that we’re here for very quickly, I promise, but Sam — from the startup ecosystem perspective, when you look back, obviously AWS, transformational, completely changed where the barrier was, now anyone can get started. You have seeds, you have angel investors, and it sort of moves back the barrier where the cutoff point, you don’t have to get servers on a PowerPoint, you can build an app and then go to your Series A or whatever it might be. What, though, is different or the same compared to what that enabled versus the world today from your perspective?
SA: I think there have been four great moments for platform enablement of startups at mass scale: there was the Internet, there was cloud, there was mobile, and then there was AI. The first one of those that I was kind of like an adult for was the cloud and in the early days of YC [Combinator] — it’s like hard to overstate what a change this meant for startups. Before, you had these startups that were like renting colo[cation] space and putting together servers and putting stuff in there and it was this like massively complex thing, and you had to like raise all this money. Then all of a sudden, even though the cloud happened like right after YC got started, I guess it was the year after.
I was just going to ask that — is it really at the end of the day, they’re really hand-in-hand more than you realized at the time?
SA: They felt incredibly hand-in-hand at the time, it felt like YC was, you know, surfing this wave of the cloud from the very beginning because there were some early pre-AWS examples.
You don’t need to put that much money into a startup to get something off the ground if AWS exists compared to what it might’ve been before.
SA: It was this huge enabling change and it was part of why YC sounded so crazy at the time. People were like, “Well, there’s no way you can fund a startup with a few tens of thousands of dollars, it’s impossible, the server costs more than that”, so it was this complete change to what startups could do with small amounts of capital.
Startups generally win when there is a big platform shift and you can do things with a faster cycle time and much less capital than before, that’s a classic way startups can beat big companies, and at the beginning of my career, I really witnessed that happen with the cloud, it actually feels quite directionally similar now watching what companies are doing building on AI, but as Matt was saying, the speed of it is crazy.
Is there a bit where the incumbents, the large companies, are adopting this way faster than they than they were the cloud?
SA: There’s definitely more of that, but I also mean just the the rate that revenue is scaling in at startups — I spoke at YC recently and I kind of asked at the end, “What are the expectations for revenue for a good company at the end of YC?”, and they’re like, “Well it’s kind of changing every month, maybe we’d have a different answer at the beginning of the batch versus the end of the batch”, and this never used to happen before. Just the rate at which people are able to build scaled business on this new platform is unlike anything I’ve seen before.
You were the cloud of choice for basically all startups, a huge advantage to that whole era, Matt. What makes you the cloud of choice today? Because you think about a lot of people building on the OpenAI API, or is that something you felt, “Actually we’re coming at this market from a very different perspective, we have a huge installed base who’s begging us to get AI things, and we have less visibility into this whole cohort that Sam’s talking about”?
MG: I think there’s a couple of things. One is, is we’re quite excited about our partnership, and I think it’s going to be really meaningful to a bunch of startups out there. But today, even if you go and you talk to startups, the vast majority of scaling startups are still scaling on AWS today, and there’s a whole bunch of reasons for that. The scale is there, the availability is there, the security is there, the reliability is there, that kind of partner ecosystem of other ISVs are in AWS, the customers are in AWS.
(laughing) Everyone’s used the AWS panel whether they wanted to or not, so they’re used to it.
MG: And we help them. We spend a ton of time enabling startups, whether it’s with credits, but it’s not just with credits, it’s advice on how to set up your systems, how to think about go-to-market, a bunch of those things that are, I think, are really appreciated by a bunch of the startups, we invest a lot of time and effort to make sure because we really feel like the startups are the lifeblood of AWS. They were from the beginning, like when Sam was talking about it, but they remain today, and I still go once a quarter out to Silicon Valley or other places to meet directly with startups to hear what they’re doing, to make sure that what we’re building is landing with them. So there is more competition today than there was 20 years ago for that startup attention, and it’s just as important for us as it’s ever been and and we spend a ton of time to make sure that we’re meeting the needs of those startups.
Is it fair to say people building directly on the OpenAI API, as opposed to say the Azure version of it, are more likely to have a stack of AWS for for regular compute and then OpenAI for for their AI?
MG: I think that’s a very common pattern that a lot of startups have today, absolutely.
Bedrock Managed Agents
Well that brings us to today’s announcement: Bedrock Managed Agents, powered by OpenAI, I think I got that right. The pitch, as I understand it, is not simply OpenAI models are available in AWS — I don’t think that’s allowed — it’s that OpenAI’s frontier models are being packaged inside an AWS-native agent runtime, identity, permission state, logging, governance, and deployment. Sam, is that the right way to articulate it?
SA: Yeah, that was pretty good.
Thank you. What is this? Now explain it in English.
SA: I think the next phase of AI is going from you supply some text to an agent and get more text back, or even you supply a bunch of code and get more code back, to we are going to have these agents running inside of a company doing all different kinds of work.
Virtual co-workers is kind of my least bad of the ways I’ve heard this described, but no one has quite figured out the right language for this, and we are packaging a new product that we’re working on together to help enable companies that want to build these sorts of stateful agents and make them available. Again, I think we don’t know exactly how the world’s going to talk about these, use these, but if you look at what’s happening [with Codex], I think there’s a great example of where we can see this all going.
How important is the harness, the runtime around the model, the tools, state — to your point, a very important word to you — memory, permissions, evals, to making agents actually work?
SA: Hard to overstate how critical it is. I no longer think of the harness and the model as these entirely separable things, like my experience of using these, I am very aware of the fact that I don’t always know when I fire something off in Codex and it does an amazing thing for me. I don’t know how much credit —
Was it that the model is amazing or the harness was amazing?
SA: Yeah, exactly.
To what extent is the harness developed in conjunction with the model? Where does that integration happen? Is it in post-training? Is it in the prompt? What makes this integration work?
SA: Both of those. It’s not really part of the pre-training process but I would say you can look at it — there’s a more interesting thing here which is the fact that we’ve seen examples of this many times in the past of where things that we thought were very separable get baked in more and more and more. Like the way we initially thought about tool-calling, which is now a critical part of how we use these models, was not something that we thought about deeply integrating into the training process and over time we’ve done more and more of that.
I would also suspect that model and harness come together more over time and I would for that matter, I would expect that pre-training and post-training eventually come together more over time as well. It’s such a cliché to say, but I’ll do it anyway, because I think it’s very, very true — we’re so early in the paradigm of all of this, this is still like the Homebrew Computer Club days of how much this is like really matured as an industry.
This is why I think so interesting, I wrote about this a few weeks ago, in any value chain, ultimately a point of integration emerges that that’s where it’s really important, these two pieces have to go together to make it work. And over time, that’s obviously where a lot of value collects — my thesis then is that this harness-model integration is the key point. It’s to your interest, but it sounds like you agree.
SA: It is to my interest, I do agree, but I also would say even more broadly, what you care about is that you go type into Codex what you want to happen and that it happens.
You don’t care about the implementation details.
SA: I don’t think you do. There have been so many examples as we’ve been figuring all of this out where we had to do something at the level of the system prompt, that later we didn’t. The general observation here is as the models get smarter, you have more flexibility to get them to behave in the ways you want which sounds like an obvious statement, but it is—
It’s easier to tell a 10-year-old what to do than a 5-year-old.
SA: When I think back to what we had to do to get any drop of utility squeezed out of these models back in the GPT-3 days that now you never would have to, because of course the model just understands and does it well out of the box, that trend may keep going much further.
MG: I was just going to add to that — I completely agree with that and I think when you talk to customers who have ideas exactly what they want these systems to do, previous to this kind of joint collaboration that we worked on together, is that customers were kind of forced to pull that together themselves, right? They wanted these models and agents to remember that they work together well and they wanted to integrate into their existing systems, and it’s not just third-party tools, it’s their own tools. They want them to learn about their own data, their own applications, and their own operating environment and all of that kind of integration today, at least, is left to every single customer to do on their own.
So part of this joint collaboration that we were leaning into together is co-building a new type of product that actually brings those things much closer together so that customers can much more easily go accomplish these things that they want to do, where identity is already kind of built into that product, where the ability to go authenticate to your database all happens inside of your AWS VPC [Virtual Private Cloud]. You can do a bunch of these things that would be possible to do if we were kind of at the OpenAI APIs and AWS over here, but by building this thing together, we make it much easier for customers to much more rapidly get to value and go accomplish the thing they want to do inside of their enterprise environment.
So you think that you can build a functional agent in a generic harness, it’s just way more difficult? You’re making it easier? Or is there a bit where actually there might not even be stuff you can do if you don’t have them tied together?
SA: To go back to your earlier analogy, pre-AWS days, you could do a lot if you were willing to go stand in a cage and buy a bunch of servers and figure out how to connect them and hire your own network engineer, and you could make a lot of things happen and then all of a sudden as soon as you could just like log into an AWS control panel and click, “I need another S3 instance”, or whatever, you could make a lot more things happen because the activation energy, the amount of work that required for the basics, got way better so you can do a lot with the models today.
Yet every time I watch someone use our models or try to set up some of this work Matt was saying, I am torn between being happy they’re so impressed and feel like this is a magical technology and pulling my hair out at how much pain and suffering they’re going through to get anything to work at all, and that’s not just true of developers building these products, even using ChatGPT and watching people copy and paste things from here to there and try to have this complicated set of prompts — I know that’s going to go away, and I’m thrilled. It’s still so early, and so bad.
Just don’t take away your integration with BBEdit, that’s all I ask, my number one favorite feature of the ChatGPT app.
SA: Fine.
(laughing) Thank you.
SA: A) This stuff is just way too hard to do, and we think if we can make it way easier it’ll bring way more value to developers and businesses, but B) there are a lot of things that you just can’t reliably get to work at all and I think through our joint collaboration not only will it be a story of ease of use and not having to go build out your own colo or whatever, we are going to jointly figure out a lot of new things to build where people will be able to build products and services that just can’t be done even with a lot of pain and suffering.
Local vs. Cloud
I actually want to come back to that point about things to be built. But just to go back to Codex real quick — Codex is a harness and model, it runs locally. Why is it easier to get agents to work locally right now?
SA: Actually, we started with it running in the cloud, and I think eventually you do want it to run in the cloud.
For sure. I’m walking through the transition to this offering, which is in the cloud. But why did you go back to local?
SA: You have your whole environment there, your computer’s set up, your data is there, you don’t have to like think about — it was just easier to get to work, even though it’s not the end state. But getting to a world where agents do run in the cloud and when you — if you have a very intensive thing, or you need to close your computer or whatever, you can hand stuff off to working on the cloud, I think is clearly going to be great. But the ease of use that we were able to deliver clearly in the short term, it won out to have it using your local environment.
There’s one way that I think about it, is like you have the old school security model, which is like the castle-and-moat sort of thing, and you’re moving to a new security model of zero trust and everything having the appropriate permission structure and authenticating and all those bits and pieces, and it feels like to me one way to frame running locally, it’s like your self-imposed castle-and-moat, everything’s on there, I just assume it’s all fine and easy to do. And a way I’m thinking about this, and Matt, let me know if that resonates with you, is to get all those pieces to actually function in a production environment you just can’t even have that all locally, you have to be operating this environment from the get-go, is that a right way to think about it?
MG: I don’t know that there’s any computing environment that’s gotten rid of a client, there are just benefits of operating locally. There’s a reason that most of your iPhone apps also have a local component, whether it’s connectivity or latency or just local compute or access to files and applications. The local client does have a particular — as Sam said, it’s easy, it works really well, it’s constrained, though, there’s limits to it.
You can’t scale out your local laptop, you have what you have and once you start getting in an enterprise contract, sharing between two people gets to be a little bit harder — thinking about permissions, thinking about security boundaries gets to be a little bit harder. So there’s a number of those pieces where I think that, I wouldn’t say that having the local environment is a bad thing, it’s just a different thing, and I think that you’re eventually going to want to have that bride across both.
That’s my question, because you have in the cloud era, you had containers that helped you converge local and production environments, but it kind of feels like in this case if you have to deal with agents, to your point, say I was like a virtual co-worker and or whatever it might be, if they have their own identity and they have their own permissions and all those sorts of things, to even build them you need to be in the right environment as you’re going to deploy it, it would seem that way to me.
SA: I think there is so much to figure out here. Just to give one example, if you’re an employee at a company, do you want to have one account for when you use some service, and then should your agent just use your account, or should your agent use a different account so that the server can tell which is which?
Or what if you want lots of agents?
SA: Exactly. I suspect that what we actually want is something we haven’t figured out yet, and maybe it’s that when Ben’s agent is logging in as Ben, it uses Ben’s account but it notes that it’s an agent and not the real Ben. We don’t even have a primitive to think about that, but we may quickly need to figure that out and and my sense is there there are going to be 50 other things like that where as we have agents join the workforce and act with increasing levels of autonomy and complexity of tasks, a lot of the mental models that we have for how software works and how access control and permissions work inside of a company or on the broader Internet, those are all just going to have to evolve.
How do you think about, Matt, in terms of security and access policies and whatnot for agents?
MG: Yeah, I do think that that’s where when you move more of these workloads into the cloud that you can have as a central organization, more controls over some of the security pieces of it. And I do think, when we talk to customers all of the time, it is what they worry about, which is, “I love the promise of what I can do with some of these really powerful models and agents, how do I make sure that I don’t have a company-ending event where I screw it up?”, and there’s the worry out there.
I think we can help with that because it these are solvable problems, they are, and I think, giving some customers confidence, “Well, it operates inside of this VPC”, and you can at least then control that boundary and know what it has access to, or it goes through this gateway, and you can give it permissions, much like you give it a role inside of the rest of your environment. These are constructs that over the last 20 years, we’ve built up a really rich set of capabilities, so that it’s not just Y Combinator startups, but it’s global banks and healthcare agencies and everybody in the world and government agencies that can use AWS and having built up all of that security structure around it, I think can help us further accelerate how they take advantage of this technology and kind of have these safeguards to run fast.
I think a lot of times when you’re in a company, particularly companies that are in risk-averse environments, having those safety guardrails where they say, “If it operates inside of the sandbox, I am excited to go fast”, can actually help many of our customers start to use these technologies for a much broader set of things.
AgentCore vs. Managed Agents
A lot of these capabilities you’re talking about that you’ve developed over 20 years and you’re trying to put it in place for agents are exposed today through AgentCore. So what is the relationship between Bedrock Managed Agents powered by OpenAI and Bedrock AgentCore?
MG: A lot of what we’ve built together is building on the building blocks of AgentCore in order to kind of pull some of these pieces together.
So there’s like a super set that sits on top of that?
MG: The AWS team and the OpenAI team used AgentCore components together with the OpenAI models and a bunch of those pieces to go and co-build this product together.
AgentCore is kind of our set of primitives that just like if with AWS, if you want to go and build our own agentic workflows, you can do that. You can have a memory component, you can have a safe execution environment, you can have a permissioning capability, and you can go and configure all of those and we have customers running those in production today that are doing really cool things.
But not with OpenAI.
MG: But not with OpenAI, they have to use different models today, that’s true. Actually, that’s not true, we have people doing it with OpenAI.
Oh, just calling to another cloud or whatever.
MG: They just call directly to the OpenAI model. So we actually absolutely have people doing it with OpenAI today, not natively inside of Bedrock, but they’re still using that. And it’s an open ecosystem where you can pull different capabilities to go build whatever you want and my bet is that people will continue to do that. We have builders out there that love to, to Sam’s analogy, love to continue to build computers at home today, even though you don’t have to do that, and even though people like to build and we think that people for a long time will build their own agents, but the vast majority of them are going to want an easier way to do it where they don’t want to have to go configure all of those pieces themselves and that’s part of what we’ve launched in this collaboration together.
Just to be super clear, you talk about this managed experience with Bedrock Managed Agents, you can also use AgentCore and pull from a model, whether on AWS or somewhere else. And just to make clear, Sam, this is a question for you, this is the distinction between OpenAI on say, Azure, where that’s just you have direct access to the API, and that is distinct from this managed service on Amazon. Is that correct?
SA: Correct, yep.
And you feel very good about that, that’s scoped correctly in all terms, it’s not going to be an issue going forward?
SA: Yeah, I think things will evolve over time, but I feel very good about this as a way to start.
Is this going to be an exclusive offering for AWS? Or do you anticipate having this sort of managed agent service on other clouds?
SA: Yeah, we’re doing this exclusively with Amazon, we’re excited about it.
How much of the exclusive is, “Look, we’re using all Amazon’s APIs, of course it’s only on Amazon”, or is this the overall idea of a managed experience, it’s not just a “We’re using Amazon APIs”, it’s, “Right now this is going to be on Amazon”?
SA: Spiritually, we want to do this as a joint effort between our companies.
Got it. The PR does say something, and this goes back to the point you mentioned, Matt, earlier about you could call out to other APIs and glue this all together yourself. In this case, the customer data stays within AWS, so what exactly does OpenAI see, what does that mean?
MG: That’s right. So the whole thing kind of stays within your VPC and so data is protected inside of the Bedrock environment.
Got it. And this is going to be running on OpenAI models through Bedrock, and these are going to be on Trainium?
MG: They’ll be through a mix of different – some of it will be on Trainium, some of it will be on GPUs.
Is that just a function of timing? Because I think as part of your announcement a couple of months ago —
MG: Some of it’s timing and capabilities, I think we’ll kind of be mixing in the different components of building the system together, using the right infrastructure for the right parts of it. But over time, more and more of it will be on Trainium.
SA: We are quite excited to get these models running on Trainium.
Trainium
One quick question, just a general question about Trainium, Matt. Trainium, is it fair to think, and this is the way I’m thinking about it, so I want to make sure I have it right. Trainium — very unfortunately named, because it’s really going to be about inference going forward — the number one manifestation will be through managed services like a Bedrock, where the customer doesn’t even necessarily know what compute they’re using, is that a fair way to think about it?
MG: Number one, I take responsibility for bad naming across all AWS services.
Look, I have a word-of-mouth site named Stratechery, so I have all sympathy for bad naming.
SA: I think Trainium is a cool word.
MG: It is a cool word.
It is a cool word, it just feels like it’s an inference chip, not a training chip.
MG: It is. But, yeah, naming aside, it is useful for both training and inference. And look, it’s a chip that we’re incredibly excited about, and both in the current generations as well as ongoing, we think that’s going to be a huge business and a real enabler for a lot of the things that we do together.
I think just with GPUs, by the way, you’re going to interact with a lot of these accelerator chips through abstractions. So the vast majority of customers don’t interact with GPUs either, except through maybe like in their laptop or something like that, for graphics. But when you’re talking to OpenAI, even if they’re running on GPUs, you’re not talking to the GPUs, if you’re talking to Claude, you’re through GPUs or Trainium or TPUs, you’re not talking to any of those chips, you’re talking to the interface. And the vast majority of inference out there is being done on one of a handful of models.
And so whether it’s 5, 10, 20, 100, it’s not millions of people that are programming to those things directly, and that’s gonna be true going forward just because these systems are so complex, they’re very large. If you’re going to go train a model, not that many people have enough money to go train a model, not that many people have the expertise to actually manage it. They’re very complicated systems, and the OpenAI team is incredible in their ability to squeeze value out of a very large compute cluster. But not that many people have the team that can do that, independent of what the chip happens to be, and so I think that that’s going to be true for all accelerator chips, honestly.
SA: Ben, I increasingly think of what we have to do as a company is to be a token factory. But what the customer cares about is that we can deliver the best unit of intelligence at the lowest price and as much of it as they want, with as much capacity as they want.
Do you think we stick with pricing as far as — pricing is based on tokens, does that make sense in the long run?
SA: No. And in fact, like there was an interesting example of this with our model that just came out, 5.5. where the per-token cost is much higher than 5.4, but it requires a hugely fewer number of tokens to get the same answer, and you actually don’t care about how many tokens the answer takes, you just want the piece of work done, and you want again a price and an amount of capacity you can have for that.
So maybe I was wrong to say “token factory”, but we’re like an intelligence factory or something. We just want as many units of intelligence for the lowest price and whether that is a bigger model running fewer tokens, a smaller model running lots of tokens, whether a GPU or Trainium or something else, whether we do any of the other kind of number of things we could do about that creatively, I don’t think customers care.
In fact, they don’t really interact with that. When you go put something into Codex or when you go build a new kind of agent in the SRE [Stateful Runtime Environment], you should never have to think about that and you should just be astonished at how much you get for how little cost.
Is the reduced token usage is that model, or is that harness?
SA: That’s mostly model, it’s a little bit harness.
Got it. Do you anticipate Matt, by the way, I asked Sam the exclusive question, do you anticipate offering a similar managed service for other models?
MG: We’re focused on doing this with OpenAI right now. We’re very excited about what we’re doing together, and the fullness of time is a long time.
The fullness of time is a long time, I’ll let you stick with that one. It’s fine, I had to ask the question.
Customer Demand
I do have a question as far as customers, Sam, to your point, both your input on this, I’m curious — when people are actually in production, where does OpenAI’s responsibility end and AWS’s begin? It sounds to me, if all the data is on AWS and it’s staying there, and they’re operating at a higher level, this is ultimately AWS’s responsibility? Is that the right way — am I thinking about that correctly from a consumer perspective?
MG: Yeah, I think that’s right. When you’re going to call somebody, you’ll call AWS support to help you out, and it’s part of your AWS environment and you build it together and your AWS account reps are going to help you there. And we’ll bring in, when we’re building it, we’ll bring in our OpenAI colleagues to help you figure out how to best take advantage of this or whatever. At some point, if we run into a bug that we need their help with, we’ll escalate over to them, but AWS will be that frontline support that you kind of interact with.
Where do you see the scale of this business, Sam, relative to your core API business?
SA: I hope it’s going to be huge, we’re putting a lot of effort into this, we’re committing to buy a lot of compute, I believe there will be a lot of revenue there to support this. The increasing framework that I’ve had is that at a low enough price, demand for intelligence is essentially uncapped.
So is it very elastic in that regard? You decrease price, demand goes up?
SA: It’s certainly that, but again, you can decrease the price of water and maybe you’ll drink a little more water, maybe you’ll shower twice a day instead of once a day, there’s some elasticity there but at some point you’re like, “You know what, I have enough water”.
Also you will buy water no matter how much it costs if you have to.
SA: Other utilities, if electricity is cheaper you’ll certainly use more of it, but if you think about intelligence as a utility, there’s no other utility I know of that I’m just like, “I just want more, I’ll just use more as long as the price is low enough, I’ll just use more”.
MG: I will say actually and interestingly it’s largely been true of compute power where if you think about the cost of a compute cycle today versus what it was 30 years ago, like I don’t even know how many orders of magnitude cheaper, and there’s more compute being sold today than ever.
Right. People don’t really think about the cost of compute at least until they’re at extremely high levels it’s a material level, but by and large strategically speaking it’s just assumed you have compute. What’s the runway to getting there with with AI where it’s not the number one thought process, “How much am I spending here?”.
SA: I don’t think that is the number one thought process. Right now we have way more customers asking us, “No matter what the price is, can you give me more? I just need more capacity, I’ll pay you extra”, than we have arguing with us about the price.
But I do think we are going to continue to bring the price down crazily dramatically, now maybe the more we do that the amount of wealth that wants to flow and just goes up more and more and more. But I am confident we will continue to be able to reduce the cost of today’s level of intelligence quite dramatically — one thing that has somewhat surprised me is how much, and I don’t know if this is going to stay the case or not, but at least today how much of the total market demand is at the absolute frontier.
Right, there’s a lot of questions about that. It’s very expensive to serve the front end, people can just get the previous one, but you’re saying people just want to be on the front end no matter what?
SA: So far they do.
MG: And I think that’s a good signal that you’re not anywhere close to where we want to be and that there’s so much more demand, and I really do think it’s like if you go 40 years ago to compute demand, a computer was crazy expensive, and now it’s dwarfed by the the power that’s in everybody’s cell phone and we sell billions more of those things. I do think that that’s what’s going to happen to the AI world where today you’re pushing, everybody wants to use the frontier because that’s what you need in order to get a lot of useful work, and everyone’s so excited about the capabilities out there.
I think over time, you will have a mix of models, by the way, where you will have some smaller models that are able to do stuff that even the latest OpenAI models aren’t able to do yet, but they will be smaller and cheaper and faster over time, and you’ll have the super big ones that are going to go try to cure cancer and other things like that. But I think we’re still at just the early stages of what’s possible and when you see this much demand and this much growth when you’re at the early stages of what’s possible, it’s exciting for what the future holds.
Is there a bit of a cynical view here where, Sam, you had a bunch of customers that are like, “We’d love to use OpenAI models, but all our stuff’s in AWS, we’re not moving”. And Matt, you’re like, “Look, all our stuff’s in AWS, can you please go get OpenAI models?”, and this is just satisfying that need — and it turns out, because AWS is the biggest, that was an astronomical amount of need. Is that just the easiest answer? Or is there a bit here, too, where you actually think you can deliver something highly differentiated that will also draw new customers for each of you?
SA: We’re clearly thrilled to get access to AWS customers, and so many people love AWS. Yeah, that is a true statement.
MG: That part is definitely true.
(laughing) Right.
MG: And vice-versa, our customers are very excited to get access to OpenAI technology.
SA: But I do think there is something incredible and new to build together, and I am hopeful that when people look back on this in a year, the most important thing people will talk about is not like, “Oh, finally, you can get access to these models via AWS”, or whatever, but it’ll be like, “Wow, we didn’t realize how important this new product was”. I think we are close at a model and harness and capability level to just a completely new kind of computing and that will feel very different than the existing ways people have thought about, “I need an API to this model”, or whatever.
MG: I couldn’t agree more, that’s exactly it. The first part is great and is nice and the second part is, I think, what we all get super excited about.
Building the AI Stack
To that point, I mentioned I want to come back to this earlier, but I have a theory, which may or may not be correct, I’m curious your guys’ point about this, about stuff to be built. Specifically, there may end up being this real middleware or middle layer of where you have all these different databases and SaaS apps and all these bits and pieces of data in an organization that can stretch across things, you have this agent layer/harness or with the harness, I guess, sitting on top, and there’s something to be built in the middle and OpenAI Frontier gets at this a little bit. Is this part of this? Or is this something to be built? Or am I totally off base and we don’t need that at all?
SA: You are totally right that we need something there. When I’ve been talking to customers recently, like large enterprises, they’re like, “I want some sort of agent runtime environment, I want a management layer where I can connect my data to agents and also make sure that I understand where I’m spending on tokens and not and have some sort of oversight there, and I want some sort of workspace” — hopefully it’ll be Codex — “something like that for my employees”, and that package of what people are asking for is getting remarkably consistent, but there is work to go off and now go build all that offering.
It feels like there’s like almost a double agent layer that’s necessary. There’s like the agent layer to maintain the middle layer that is constantly spelunking down in all these data sources and then there’s the actual user interface layer that is where people are actually interacting with. Does that sort of fit with where we’re going or is that off base?
SA: On both of those, I agree that that’s a picture of how the world looks today. As the models get really smart, I don’t think we know exactly what the architecture of the future is going to look like.
Right now people do, at this sort of call it user agent layer, want to interact with multiple agents and we make it so that you can build agents for this thing and that thing and they can talk together and whatever else and then at the company management layer, people have all these controls about how you help the AI go spelunk and files in file systems.
And at some point you realize that you’re just holding on to the past for no reason at all, this should just be in the model.
SA: That’s what I was going to say. At some point, you may say, “Actually, we have such incredible capabilities, let’s re-architect the whole thing”.
MG: Yeah, I agree. And I think there’s something different, and I’m not sure we all know what it is yet, but that’s part of the beauty also, is you get customers using and building and you can learn from them and figure out how you can make that easier, faster, better for them.
Sam, this is the second time we’ve done one of these product launch interviews, last time it was with Kevin Scott and New Bing — you were pretty confident about the threat you posed to Google then, how well do you think that worked out?
SA: I think we have done better than I expected. ChatGPT is, I think, the first really large-scale new consumer product since Facebook.
Is that actually the answer, you’ve done better than you expected, but it manifested mostly through ChatGPT as opposed to other other areas?
SA: No, I think we’ve also done quite well on the API, particularly on Codex, but that was not what I was thinking at the time. At the time, I was thinking maybe these new kinds of language interfaces are going to change the way people find information on the the Internet and you know — Google, also just absolutely phenomenal company, I think in many ways Google is still underrated just in terms of the breadth and depth of what they do, but I am happy with how ChatGPT has performed relatively.
I actually have a Google question for you Matt, in a similar way. Google was just up there this week, Thomas Kurian talking about their fully integrated stack, all the way up and down from model to chip to to agent layer, all that sort of thing. You’re here with another company executive, definitionally not fully integrated within Amazon, but is there a bit where everyone was critical of you not having a frontier edge model — now that we’re in this sort of inference area, you’re used to serving a lot of companies. Did you maybe end up in a better spot by being neutral in a way? Was that on purpose or did you accidentally end up in a great place that you didn’t realize it was going to be?
MG: A little bit on purpose. We, since we started AWS, we have always embraced our partners as a key part of us supporting our end customers. Since the very beginning, it’s been an incredibly important part of our strategy is to lean in with partners and maybe different than some others, we view our success is if the partners are successful and they’re building on top of us or together with us, and if they’re successful, then we’re successful, that’s awesome.
We view it as that’s growing the pie together, then that’s a win, and it’s not necessarily how others view the world. Sometimes they say, “I have to own everything”, and that’s okay, that’s a view that people have. But I think that choice is important, and that way the best products win. And by the way, you can have first-party products in that world, you can have lots of third-party products in that world, but our view is we want the customers to be able to pick the best thing for them. And if the best thing is your own stuff that you’re building, awesome.
For us, if the best thing is what our partners are building, but it’s on top of us, we view that as a win as well, it’s because it’s the best thing for our customers. We’ve long thought that, and it’s actually how we built the Bedrock platform in the AI world. We want to support a broad set of models, we want to support a broad set of capabilities, and it’s true, it’s been true across from databases to compute platforms to other things like that.
So I think it’s been an intentional strategy, I think it’s a strategy that customers appreciate because they like that, and we’re excited to continue to lean into it.
Yeah, it’s interesting. There’s the balance between software, platform, infrastructure, and everyone says they’ll serve everyone. But it does feel like you go way back when AWS started, it’s like you start with the I [Infrastructure], and that gives you almost – that gives you the greatest flexibility, it feels like, from my perspective, to meet Sam in the middle. Sam’s got a great S [Software], you guys are building a P [Platform] together, I guess is the way to put it.
MG: That’s right. It does make it hard where you say, “We have one S3”, there’s not other S3 offerings, that part is true. So some of those core components are, like you said, at the infrastructure layer, we do lean in pretty heavily on the stuff that we build. But as you move up that stack, I think there’s a broader set of capabilities and if you view the world that — in no world do I think any one company is going to own every application and as you get further down the stack, when you get to kind of the models and services layer, there’s fewer of those and you get down the infrastructure, there’s even fewer of those and our view is kind of embracing that whole set of partners is great for us end customers.
Sam, any final words?
SA: I think that was very well put. I really do think there’s a potential at a new generation of the kinds of products that developers can now build and given how steep we expect model capability progress to be over the next year, the fact that we’re going to go on this journey together and try to really build a platform to enable it, is coming at a good time, and I think people are going to love it.
Very good. Matt, Sam, thanks for coming on Stratechery.
MG: Awesome. Thanks for having us.
SA: Thank you.
This Daily Update Interview is also available as a podcast. To receive it in your podcast player, visit Stratechery.
The Daily Update is intended for a single recipient, but occasional forwarding is totally fine! If you would like to order multiple subscriptions for your team with a group discount (minimum 5), please contact me directly.
Thanks for being a supporter, and have a great day!
