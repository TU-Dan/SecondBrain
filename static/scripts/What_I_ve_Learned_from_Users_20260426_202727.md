# What I've Learned from Users

**生成时间**: 2026-04-26 20:27

---

| |
2022年9月
我最近告诉Y Combinator的申请者，我能给出的最精炼的录取建议是：
解释你从用户那里学到了什么。
这能检验很多事情：你是否关注用户，你对他们的理解有多深，甚至他们对你正在开发的产品有多需要。
之后我问了自己同样的问题。我从YC的用户——我们资助的初创公司——那里学到了什么？
首先想到的是，大多数初创公司都有相同的问题。没有两家公司的问题完全相同，但令人惊讶的是，无论它们开发什么，问题在很大程度上保持不变。一旦你为100家做不同事情的初创公司提供过建议，你很少会遇到以前没见过的问题。
这个事实是YC成功的原因之一。但我们在创办YC时并不知道这一点。我只有少数几个数据点：我们自己的初创公司，以及朋友创办的那些。令我惊讶的是，同样的问题经常以不同形式重复出现。许多后期投资者可能永远不会意识到这一点，因为后期投资者在整个职业生涯中可能不会为100家初创公司提供建议，但YC合伙人会在头一两年内获得这么多经验。
这就是资助大量早期公司而非少量后期公司的一个优势。你会获得大量数据。不仅因为你关注了更多公司，还因为更多问题会出错。
但知道初创公司可能遇到的（几乎）所有问题，并不意味着提供建议可以自动化或简化为一个公式。与YC合伙人进行个别办公时间是不可替代的。每家初创公司都是独特的，这意味着它们必须由了解它们的特定合伙人提供建议。
[1]
我们是在2012年夏天臭名昭著的“搞垮YC的那批”中艰难学到这一点的。在那之前，我们把合伙人当作一个资源池。当一家初创公司预约办公时间时，他们会得到任何合伙人发布的下一个可用时段。这意味着每个合伙人都必须了解每家初创公司。这在60家初创公司时运行良好，但当批次增加到80家时，一切都崩溃了。创始人可能没有意识到任何问题，但合伙人感到困惑和不快，因为批次进行到一半时，他们仍然不了解所有公司。
[2]
起初我很困惑。为什么60家初创公司时一切正常，而80家时就崩溃了？只多了三分之一。然后我意识到发生了什么。我们使用的是O(n²)算法。所以它当然会崩溃。
我们采用的解决方案是这类情况下的经典做法。我们将批次分成更小的初创公司组，每组由一组专门的合伙人监督。这解决了问题，并且从那以后一直运行良好。但搞垮YC的那批有力地证明了为初创公司提供建议的过程必须多么个性化。
另一个相关的意外是，创始人有时很难意识到自己的问题是什么。创始人有时会进来讨论某个问题，而我们却发现另一个更大的问题。

谈话过程中。例如（这种情况太常见了），创始人会来谈论他们在融资时遇到的困难，而深入了解他们的处境后，结果发现原因是公司经营不善，而投资者能看出来。或者创始人会来担心他们仍未解决用户获取的问题，而原因其实是他们的产品不够好。有时候我会问：“如果不是你亲手做的，你自己会用这个产品吗？”创始人思考后说：“不会。”那么，这就是你难以获取用户的原因。

创始人通常知道自己的问题是什么，但不知道它们的相对重要性。

[3]

他们会来谈论自己正在担心的三个问题。其中一个问题重要性中等，一个完全无关紧要，还有一个如果不立即解决就会毁掉公司。这就像看恐怖电影，女主角对男友出轨深感不安，却对那扇神秘虚掩的门只有轻微的好奇。你想说：别管你男友了，想想那扇门！好在办公时间你可以这么说。所以尽管创业公司仍会定期倒闭，但很少是因为他们走进了有凶手的房间。YC的合伙人可以警告他们凶手在哪里。

但创始人并不总是听劝。这是另一个大惊喜：创始人有多频繁地不听我们的话。几周前，我和一位在YC工作了几期、开始看出规律的合伙人聊天。“一年后他们回来，”她说，“说‘真希望当初听了你们的话。’”

我花了很长时间才弄明白创始人为什么不听劝。起初我以为只是固执。这是部分原因，但另一个可能更重要的原因是，关于创业公司的很多事情都是反直觉的。

当你告诉某人反直觉的事情时，他们听起来会觉得是错的。所以创始人之所以不听我们的话，是因为他们不相信我们。至少要到经验教训让他们改变看法为止。

[4]

创业公司之所以如此反直觉，是因为它们与大多数人的其他经历截然不同。除了亲身经历过的人，没人知道那是什么感觉。这就是为什么YC的合伙人通常自己也得是创始人。但奇怪的是，创业公司的反直觉性恰恰是让YC运转的另一个因素。如果它不反直觉，创始人就不需要我们的建议来指导如何创业。

专注对早期创业公司来说加倍重要，因为他们不仅有一百个不同的问题，而且除了创始人自己，没有人能去解决这些问题。如果创始人专注于无关紧要的事情，就没人去关注真正重要的事情。所以YC工作的本质就是找出哪些问题最重要，然后构思解决方案——理想情况下以一周或更短的时间为周期——然后尝试这些方案并

衡量它们的效果如何。重点在于行动，以及可衡量的、近期的成果。

这并不意味着创始人应该不顾后果地向前冲。如果你以足够高的频率修正方向，你就可以在微观尺度上果断决策，同时在宏观尺度上保持试探性。结果是一条有些曲折的道路，但执行速度非常快，就像跑卫在球场上的跑动路线。实际上，走回头路的情况比你预想的要少。创始人通常能猜对应该往哪个方向跑，尤其是当他们有像YC合伙人这样经验丰富的人可以与之探讨假设时。而当他们猜错时，他们也能很快察觉，因为他们会在下周的办公时间讨论结果。

[5]
导航能力的小幅提升能让你快很多，因为它有双重效果：路径更短，而且当你更确信这是正确路径时，你也能沿着它跑得更快。这就是YC的很大一部分价值所在——帮助创始人获得额外的专注力，从而让他们行动更快。而由于快速行动是初创公司的本质，YC实际上让初创公司变得更像初创公司。

速度定义了初创公司。专注力带来了速度。YC提升了专注力。

为什么创始人会不确定该做什么？部分原因是，初创公司几乎在定义上就是在做新的事情，这意味着还没有人知道该怎么做，或者在大多数情况下，甚至不知道“它”是什么。部分原因是初创公司通常非常反直觉。还有部分原因是，许多创始人，尤其是年轻且雄心勃勃的创始人，被训练成了以错误的方式获胜。我花了好几年才弄明白这一点。大多数国家的教育体系训练你通过破解考试来获胜，而不是真正去做它本应衡量的那些事。但当你创办一家初创公司时，这一套就行不通了。所以YC所做的部分工作就是重新训练创始人，让他们停止试图破解考试。（这需要的时间长得惊人。一年过去了，你仍然会看到他们回归旧习惯。）

YC不仅仅是更有经验的创始人传递他们的知识。它更像是专业化而非学徒制。YC合伙人和创始人的知识形态不同：让创始人去掌握YC合伙人所拥有的关于初创公司问题的百科全书式知识并不值得，就像让YC合伙人去掌握创始人拥有的深度领域知识也不值得一样。这就是为什么有经验的创始人参加YC仍然有价值，就像有经验的运动员仍然需要教练一样。

YC给创始人的另一大收获是同事，这可能比合伙人的建议更重要。如果你回顾历史，伟大的工作总是聚集在特定的地方和机构：15世纪末的佛罗伦萨、19世纪末的哥廷根大学、罗斯时期的《纽约客》、贝尔实验室、施乐帕克研究中心。无论你有多优秀，优秀的同事会让你变得更好。事实上，非常有野心的人可能比任何人都更需要同事。

因为他们日常生活中太缺乏这些了。  
无论YC有朝一日能否与那些著名的集群并列，它都不会是因为缺乏尝试。我们非常清楚这一历史现象，并有意将YC设计成这样一个集群。到如今，说它是伟大创业者的最大集群已非自夸。就连试图攻击YC的人也承认这一点。  

同事和创业创始人是世界上最强大的两股力量，因此你可能会认为将它们结合起来会产生巨大影响。在YC出现之前，就人们对此问题的思考程度而言，大多数人认为它们无法结合——孤独是独立的代价。这正是我们20世纪90年代在波士顿创办自己的初创公司时的感受。我们有几个年长的人可以请教（建议质量参差不齐），但没有同龄人。没有人可以和我们一起哀叹投资者的不当行为，或一起推测技术的未来。我经常告诉创始人们要做他们自己想要的东西，而YC无疑正是如此：它被设计成我们当初创办初创公司时想要的样子。  

我们想要的一件事是能够获得种子资金，而不必四处拜访随机遇到的富人。这现在已成为一种商品，至少在美国是这样。但优秀的同事永远不可能成为商品，因为他们集中在某些地方的事实意味着他们在其他地方相应地缺失。然而，在他们聚集的地方，神奇的事情发生了。YC晚宴上房间里的能量是我从未体验过的。我们当初只要能有一两家其他初创公司可以交谈就会很高兴。当你拥有满满一屋子人时，那完全是另一回事。  

YC的创始人们不仅互相激励。他们还互相帮助。这是我了解到的关于创业创始人最令人欣慰的事情：他们在互相帮助时可以多么慷慨。我们在第一批中注意到了这一点，并有意识地设计YC来放大它。结果比大学之类的要强烈得多。在合伙人、校友和同批学员之间，创始人们被愿意且能够帮助他们的人所包围。  

注释  
[1]  
这就是为什么我从来不喜欢人们把YC称为“训练营”。它像训练营一样紧张，但在结构上相反。不是每个人都做同样的事情，而是他们各自与YC合伙人交谈，以找出他们特定初创公司的需求。  

[2]  
当我说2012年夏季批次有问题时，我的意思是合伙人们感觉有些不对劲。事情还没有糟糕到让初创公司体验更差的程度。事实上，那批表现得异常出色。  

[3]  
这种情况让我想起研究表明人们回答问题的能力远高于判断自己答案准确性的能力。这两种现象感觉非常相似。  

[4]  
Airbnb的人特别善于倾听——部分是因为他们灵活且有纪律，但也因为他们

在之前的一年里经历了如此艰难的时期。他们已经准备好
倾听。
[5]
决断力的最佳单位取决于获得结果所需的时间，而这又取决于你正在
解决的问题类型。当你与投资者谈判时，可能只需要几天时间，而如果你在制造硬件，则可能需要几个月。
感谢 Trevor Blackwell、Jessica Livingston、
Harj Taggar 和 Garry Tan 阅读本文的草稿。

---

| |
September 2022
I recently told applicants to Y Combinator that the best advice I
could give for getting in, per word, was
Explain what you've learned from users.
That tests a lot of things: whether you're paying attention to
users, how well you understand them, and even how much they need
what you're making.
Afterward I asked myself the same question. What have I learned
from YC's users, the startups we've funded?
The first thing that came to mind was that most startups have the
same problems. No two have exactly the same problems, but it's
surprising how much the problems remain the same, regardless of
what they're making. Once you've advised 100 startups all doing
different things, you rarely encounter problems you haven't seen
before.
This fact is one of the things that makes YC work. But I didn't
know it when we started YC. I only had a few data points: our own
startup, and those started by friends. It was a surprise to me how
often the same problems recur in different forms. Many later stage
investors might never realize this, because later stage investors
might not advise 100 startups in their whole career, but a YC partner
will get this much experience in the first year or two.
That's one advantage of funding large numbers of early stage companies
rather than smaller numbers of later-stage ones. You get a lot of
data. Not just because you're looking at more companies, but also
because more goes wrong.
But knowing (nearly) all the problems startups can encounter doesn't
mean that advising them can be automated, or reduced to a formula.
There's no substitute for individual office hours with a YC partner.
Each startup is unique, which means they have to be advised
by specific partners who know them well.
[1]
We learned that the hard way, in the notorious "batch that broke
YC" in the summer of 2012. Up till that point we treated the partners
as a pool. When a startup requested office hours, they got the next
available slot posted by any partner. That meant every partner had
to know every startup. This worked fine up to 60 startups, but when
the batch grew to 80, everything broke. The founders probably didn't
realize anything was wrong, but the partners were confused and
unhappy because halfway through the batch they still didn't know
all the companies yet.
[2]
At first I was puzzled. How could things be fine at 60 startups and
broken at 80? It was only a third more. Then I realized what had
happened. We were using an O(n2) algorithm. So of course it blew
up.
The solution we adopted was the classic one in these situations.
We sharded the batch into smaller groups of startups, each overseen
by a dedicated group of partners. That fixed the problem, and has
worked fine ever since. But the batch that broke YC was a powerful
demonstration of how individualized the process of advising startups
has to be.
Another related surprise is how bad founders can be at realizing
what their problems are. Founders will sometimes come in to talk
about some problem, and we'll discover another much bigger one in
the course of the conversation. For example (and this case is all
too common), founders will come in to talk about the difficulties
they're having raising money, and after digging into their situation,
it turns out the reason is that the company is doing badly, and
investors can tell. Or founders will come in worried that they still
haven't cracked the problem of user acquisition, and the reason turns out
to be that their product isn't good enough. There have been times
when I've asked "Would you use this yourself, if you hadn't built
it?" and the founders, on thinking about it, said "No." Well, there's
the reason you're having trouble getting users.
Often founders know what their problems are, but not their relative
importance.
[3]
They'll come in to talk about three problems
they're worrying about. One is of moderate importance, one doesn't
matter at all, and one will kill the company if it isn't addressed
immediately. It's like watching one of those horror movies where
the heroine is deeply upset that her boyfriend cheated on her, and
only mildly curious about the door that's mysteriously ajar. You
want to say: never mind about your boyfriend, think about that door!
Fortunately in office hours you can. So while startups still die
with some regularity, it's rarely because they wandered into a room
containing a murderer. The YC partners can warn them where the
murderers are.
Not that founders listen. That was another big surprise: how often
founders don't listen to us. A couple weeks ago I talked to a partner
who had been working for YC for a couple batches and was starting
to see the pattern. "They come back a year later," she said, "and
say 'We wish we'd listened to you.'"
It took me a long time to figure out why founders don't listen. At
first I thought it was mere stubbornness. That's part of the reason,
but another and probably more important reason is that so much about
startups is counterintuitive.
And when you tell someone something
counterintuitive, what it sounds to them is wrong. So the reason
founders don't listen to us is that they don't believe us. At
least not till experience teaches them otherwise.
[4]
The reason startups are so counterintuitive is that they're so
different from most people's other experiences. No one knows what
it's like except those who've done it. Which is why YC partners
should usually have been founders themselves. But strangely enough,
the counterintuitiveness of startups turns out to be another of the
things that make YC work. If it weren't counterintuitive, founders
wouldn't need our advice about how to do it.
Focus is doubly important for early stage startups, because not
only do they have a hundred different problems, they don't have
anyone to work on them except the founders. If the founders focus
on things that don't matter, there's no one focusing on the things
that do. So the essence of what happens at YC is to figure out which
problems matter most, then cook up ideas for solving them — ideally
at a resolution of a week or less — and then try those ideas and
measure how well they worked. The focus is on action, with measurable,
near-term results.
This doesn't imply that founders should rush forward regardless of
the consequences. If you correct course at a high enough frequency,
you can be simultaneously decisive at a micro scale and tentative
at a macro scale. The result is a somewhat winding path, but executed
very rapidly, like the path a running back takes downfield. And in
practice there's less backtracking than you might expect. Founders
usually guess right about which direction to run in, especially if
they have someone experienced like a YC partner to bounce their
hypotheses off. And when they guess wrong, they notice fast, because
they'll talk about the results at office hours the next week.
[5]
A small improvement in navigational ability can make you a lot
faster, because it has a double effect: the path is shorter, and
you can travel faster along it when you're more certain it's the
right one. That's where a lot of YC's value lies, in helping founders
get an extra increment of focus that lets them move faster. And
since moving fast is the essence of a startup, YC in effect makes
startups more startup-like.
Speed defines startups. Focus enables speed. YC improves focus.
Why are founders uncertain about what to do? Partly because startups
almost by definition are doing something new, which means no one
knows how to do it yet, or in most cases even what "it" is. Partly
because startups are so counterintuitive generally. And partly
because many founders, especially young and ambitious ones, have
been trained to win the wrong way. That took me years to figure
out. The educational system in most countries trains you to win by
hacking the test
instead of actually doing whatever it's supposed
to measure. But that stops working when you start a startup. So
part of what YC does is to retrain founders to stop trying to hack
the test. (It takes a surprisingly long time. A year in, you still
see them reverting to their old habits.)
YC is not simply more experienced founders passing on their knowledge.
It's more like specialization than apprenticeship. The knowledge
of the YC partners and the founders have different shapes: It
wouldn't be worthwhile for a founder to acquire the encyclopedic
knowledge of startup problems that a YC partner has, just as it
wouldn't be worthwhile for a YC partner to acquire the depth of
domain knowledge that a founder has. That's why it can still be
valuable for an experienced founder to do YC, just as it can still
be valuable for an experienced athlete to have a coach.
The other big thing YC gives founders is colleagues, and this may
be even more important than the advice of partners. If you look at
history, great work clusters around certain places and institutions:
Florence in the late 15th century, the University of G�ttingen in
the late 19th, The New Yorker under Ross, Bell Labs, Xerox PARC.
However good you are, good colleagues make you better. Indeed, very
ambitious people probably need colleagues more than anyone else,
because they're so starved for them in everyday life.
Whether or not YC manages one day to be listed alongside those
famous clusters, it won't be for lack of trying. We were very aware
of this historical phenomenon and deliberately designed YC to be
one. By this point it's not bragging to say that it's the biggest
cluster of great startup founders. Even people trying to attack YC
concede that.
Colleagues and startup founders are two of the most powerful forces
in the world, so you'd expect it to have a big effect to combine
them. Before YC, to the extent people thought about the question
at all, most assumed they couldn't be combined — that loneliness
was the price of independence. That was how it felt to us when we
started our own startup in Boston in the 1990s. We had a handful
of older people we could go to for advice (of varying quality), but
no peers. There was no one we could commiserate with about the
misbehavior of investors, or speculate with about the future of
technology. I often tell founders to make something they themselves
want, and YC is certainly that: it was designed to be exactly what
we wanted when we were starting a startup.
One thing we wanted was to be able to get seed funding without
having to make the rounds of random rich people. That has become a
commodity now, at least in the US. But great colleagues can never
become a commodity, because the fact that they cluster in some
places means they're proportionally absent from the rest.
Something magical happens where they do cluster though. The energy
in the room at a YC dinner is like nothing else I've experienced.
We would have been happy just to have one or two other startups to
talk to. When you have a whole roomful it's another thing entirely.
YC founders aren't just inspired by one another. They also help one
another. That's the happiest thing I've learned about startup
founders: how generous they can be in helping one another. We noticed
this in the first batch and consciously designed YC to magnify it.
The result is something far more intense than, say, a university.
Between the partners, the alumni, and their batchmates, founders
are surrounded by people who want to help them, and can.
Notes
[1]
This is why I've never liked it when people refer to YC as a
"bootcamp." It's intense like a bootcamp, but the opposite in
structure. Instead of everyone doing the same thing, they're each
talking to YC partners to figure out what their specific startup
needs.
[2]
When I say the summer 2012 batch was broken, I mean it felt
to the partners that something was wrong. Things weren't yet so
broken that the startups had a worse experience. In fact that batch
did unusually well.
[3]
This situation reminds me of the research showing that people
are much better at answering questions than they are at judging how
accurate their answers are. The two phenomena feel very similar.
[4]
The Airbnbs were
particularly good at listening — partly
because they were flexible and disciplined, but also because they'd
had such a rough time during the preceding year. They were ready
to listen.
[5]
The optimal unit of decisiveness depends on how long it takes
to get results, and that depends on the type of problem you're
solving. When you're negotiating with investors, it could be a
couple days, whereas if you're building hardware it could be months.
Thanks to Trevor Blackwell, Jessica Livingston,
Harj Taggar, and Garry Tan for reading drafts of this.
|
|
