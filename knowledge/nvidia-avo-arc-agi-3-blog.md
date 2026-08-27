# NVIDIA AVO Reaches 100% on ARC-AGI-3, Demonstrating a Frontier-Level General-Purpose Architecture for Long-Horizon Autonomous Agents

> **Source** : <https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/>
> **Éditeur** : NVIDIA Technical Blog
> **Auteurs** : Terry Chen, Yeyin (Eva) Zhu, Zhifan Ye, Jean-Francois Puget, Humphrey Shi
> **Publié le** : 2026-08-21 — **Récupéré le** : 2026-08-27
> Export Markdown fidèle au contenu original de l'article (images locales sous `images/nvidia-avo-blog/`).

---

A frontier language model is only one component of an [AI agent](<https://www.nvidia.com/en-us/ai/>). The surrounding agent system—often called a harness—determines how the model receives context, uses tools, maintains state, responds to feedback, recovers from failure, and sustains progress over long-running tasks. The challenge is how to build the agent architecture that makes frontier language models work reliably on extended, multistep tasks.

The NVIDIA research project [Agentic Variation Operators (AVO)](<https://arxiv.org/abs/2603.24517>) addresses this challenge of building a general-purpose agent architecture. AVO was first demonstrated on difficult software engineering and GPU-kernel optimization tasks, where success requires far more than generating code in a single response. An agent must inspect existing implementations, form hypotheses, make changes, execute hardware-grounded tests, interpret feedback, and repeatedly revise its approach.

This post introduces the AVO architecture and the system-level mechanisms that enable it to sustain long-running autonomous work. We first summarize its application to GPU-kernel optimization, then describe how the same architecture was adapted to the ARC-AGI-3 benchmark and present the resulting public-set performance, efficiency, and key lessons.

## What is AVO?

AVO is a general-purpose coding agent system developed by NVIDIA. Like modern coding agents, AVO can inspect and edit code, run commands, consult documentation, and validate its work through execution. Its distinguishing focus is sustained autonomous operation across long horizons.

In our GPU-kernel optimization work, AVO replaces the predefined variation step of conventional evolutionary-search systems with an autonomous agent that decides how to generate the next candidate—what to inspect, what to change, what to test, and what to commit. For ARC-AGI-3, we connected the same general-purpose agent to a different task interface. The underlying agent remains the same; only the environment-specific tools and evaluation change.

![Diagram of the AVO architecture showing inputs to the agent, an iterative loop for inspecting context, planning, implementing, and evaluating candidates, persistent memory and tools, candidate selection and lineage updates, and a supervisor monitoring progress.
](images/nvidia-avo-blog/nvidia-avo-architecture-long-horizon-autonomous-agent-work.webp) _Figure 1. AVO architecture for long-horizon autonomous agent work. The main agent iteratively inspects context, plans, implements changes, and evaluates results using persistent memory and tools, while a supervisor monitors the broader search trajectory and can intervene when progress stalls_

## Improving performance with autonomous GPU-kernel optimization

GPU-kernel optimization provided an early demanding test of this architecture.

The search space is large, the performance landscape is difficult to reason about directly, and small implementation changes can affect correctness, memory behavior, scheduling, and throughput in ways that are hard to predict without execution.

In our attention-kernel study, AVO operated continuously for seven days, explored more than 500 optimization directions, and produced 40 committed kernel versions.

On [NVIDIA DGX B200](<https://www.nvidia.com/en-us/data-center/dgx-b200/>) systems, the resulting multihead attention kernels outperformed cuDNN by up to 3.5% and FlashAttention-4 by up to 10.5% across the evaluated configurations. The agent subsequently adapted the evolved kernel to grouped-query attention in approximately 30 minutes of additional autonomous work.

Beyond the final kernel performance, this experiment demonstrates that AVO can sustain a productive engineering loop over many iterations without requiring each step to be manually prescribed. More broadly, AVO reinforces a system-level view of agent design: building a [trusted agent stack](<https://developer.nvidia.com/blog/where-security-fits-in-an-ai-agent-stack/>) requires performance, reliability, and security to be designed across the full system—not treated as properties of the model alone. This same principle also shapes how we think about securing the AI agent stack. 

## Sustaining long-running agentic work

AVO is designed to preserve progress beyond a single model context. Two mechanisms are particularly important: persistent memory and supervision.

Persistent memory carries forward prior implementations, evaluation results, compiler and profiler outputs, and accumulated reasoning, allowing the agent to resume from the current state rather than repeatedly reconstructing the search.

The supervisor monitors the broader trajectory for stagnation or repeated unproductive cycles and can redirect the main agent toward alternative strategies when needed. During the seven-day attention-kernel run, the main agent remained responsible for deciding what to inspect, change, test, and evaluate, while the supervisor helped maintain forward progress when the search plateaued.

## Evolving from high-performance engineering to general-purpose reasoning

The NVIDIA team recently applied the same underlying AVO architecture to a very different challenge: the interactive reasoning benchmark [ARC-AGI-3](<https://arcprize.org/arc-agi/3>), in which agents enter unfamiliar environments without instructions, stated rules, or stated goals.

AVO achieved a 100.00 RHAE score across all 25 environments in the ARC-AGI-3 public set, completing all 183 levels. The result illustrates a broader point: evaluating a model is not the same as evaluating an agent. Model capability matters enormously, but the surrounding system determines how effectively that capability can be converted into sustained autonomous progress.

GPU-kernel optimization and the ARC-AGI-3 benchmark appear very different on the surface.

One involves source code, compilers, profilers, and throughput. The other involves unfamiliar interactive environments in which an agent must infer the effects of available actions, discover objectives, and act efficiently enough to make progress.

But the underlying computational pattern is similar. In both settings, the agent must:

  * Build hypotheses from incomplete evidence
  * Take actions through an external interface
  * Observe the consequences
  * Preserve useful state
  * Revise its model of the problem
  * Recover from incorrect assumptions
  * Continue making progress over a long horizon

The domain changes. The feedback channel changes. The core agent loop does not.

What transfers is not domain knowledge, but the machinery for sustained autonomous progress. 

For this reason, ARC-AGI-3 provided a useful test of whether the AVO architecture was fundamentally tied to software engineering or captured something more general.

![Animation showing AVO completing all the 25 games of ARC-AGI-3 public set. Each game has 6 to 10 levels, totaling 183 levels.
](images/nvidia-avo-blog/ARC-AGI-3-benchmark-nvidia-avo-public-set-games.gif) _Figure 2. AVO achieved a 100.00 RHAE score across all 25 game environments in the ARC-AGI-3 public set, completing all 183 levels_

## Evaluating AVO on ARC-AGI-3

ARC-AGI-3 is an interactive reasoning benchmark. An agent enters unfamiliar game-like environments without instructions, explicit rules, or a stated goal. It must explore through interaction, infer the environment’s dynamics and objectives, and plan actions efficiently across progressively harder levels.

The benchmark uses [Relative Human Action Efficiency (RHAE)](<https://docs.arcprize.org/methodology>), a metric that combines task completion with per-level action efficiency relative to first-time human baselines. Performance is aggregated across levels and environments.

This metric makes ARC-AGI-3 a demanding long-horizon agent task. Success requires more than solving an isolated state. The agent must preserve useful knowledge, learn from previous interactions, recover from mistakes, and spend environment actions efficiently.

Rather than centering our ARC-AGI-3 system on explicit programmatic world-model construction, as explored by[ Tycho](<https://github.com/NIMI-research/Tycho>), we adopted the direct-interaction design principles described by [VISTA](<https://vista-research.github.io/>) and reimplemented the task interface independently. This was better aligned with our goal of evaluating AVO as a general-purpose agent rather than introducing an ARC-specific world-model layer. 

Several elements of the task interface were informed by VISTA, but the agent backend was fundamentally different. VISTA instantiates the harness with Claude Opus 5 through Claude Code or GPT-5.6 Sol through Codex, whereas our system uses AVO, the NVIDIA long-horizon agent architecture with persistent memory, supervision, and its own execution loop.

The observation interface also differs. VISTA’s primary configuration uses a rendered 512 x 512 PNG, while also exploring textual-grid representations. In the AVO configuration, the LLM operated in a text-only modality: each observation was supplied as an exact 64 x 64 text grid, with no images or image tokens sent to the model. Consistent with the direct-interaction setup, the agent received the available actions without descriptions of the game’s rules or goals and had to infer their effects through interaction.

## AVO performance results on the ARC-AGI-3 benchmark

Recent ARC-AGI-3 systems have explored substantially different agent architectures, from explicit executable world models such as Tycho to direct-interaction harnesses such as VISTA. Together, these results highlight that benchmark performance reflects the complete agent system, not only the underlying model. 

Using Claude Opus 5, AVO completed the full 25-environment public set with a 100.00 RHAE score, solving all 183 levels in 6,624 environment actions. For reference, VISTA reports 7,542 environment actions with Claude Opus 5 while completing the same 183 public-set levels. AVO therefore used approximately 12% fewer actions in this cross-system comparison. 

This should not be interpreted as a controlled ablation: the two systems differ in agent backend, observation representation, memory, context management, and other implementation details. One architectural difference that may matter over long horizons is the AVO memory system, which is designed to carry useful understanding forward and reduce repeated exploration, although this experiment does not isolate its individual contribution.

[ARC Prize](<https://arcprize.org/results/anthropic-claude-opus-5>) separately reports approximately 30% for Claude Opus 5 at High reasoning effort. Our run used the same model family under a different reasoning setting and a substantially different agent system and evaluation setup. These numbers therefore should not be interpreted as a direct measurement of the performance contribution of AVO; rather, they illustrate that model-level evaluation alone does not characterize the performance of a complete agent.

AVO is also designed to operate across frontier models. While our full public-set result used Claude Opus 5, we additionally paired AVO with GPT-5.6 Sol on a challenging subset of games. In these limited experiments, Sol reached matched levels faster in wall-clock time in several cases, while Opus used fewer environment actions in matched-level comparisons. These preliminary results suggest complementary operating profiles across models, and we leave a broader systematic comparison to future work.

These results cover the 25-environment ARC-AGI-3 public set using the official scorecard and RHAE metric. They are not results on the semi-private or fully private competition sets.

## What we learned from benchmarking AVO on ARC-AGI-3

The most important result was not simply the 100.00 score, but that the same agent architecture transferred from highly specialized GPU-kernel optimization to a very different interactive reasoning task.

In GPU optimization, feedback comes from compilers, tests, profilers, and performance benchmarks. In ARC-AGI-3, feedback comes from environment transitions and action outcomes. The interfaces differ, but the loop is the same: form a hypothesis, act, observe evidence, update state, and continue.

This suggests that generality can come not only from domain knowledge, but from the machinery that allows reasoning and feedback to compound over time.

More broadly, long-horizon capability is a property of the full system. Memory determines what survives, tools determine what actions are possible, feedback grounds progress, and recovery allows work to continue beyond a single model invocation.

## Looking ahead

NVIDIA AVO research began with autonomous software engineering and high-performance GPU-kernel optimization. ARC-AGI-3 shows that the same underlying architecture can transfer to a very different reasoning environment.

The larger opportunity is to build general-purpose agent systems around persistent state, tool use, grounded feedback, recovery, and long-horizon context management—systems that can accumulate evidence and sustain progress across increasingly diverse tasks.

The model matters, but the model is not the entire agent.

To learn more, check out these resources:

  * Read the paper, [AVO: Agentic Variation Operators for Autonomous Evolutionary Search](<https://arxiv.org/pdf/2603.24517>)
  * Explore the [ARC-AGI-3 benchmark](<https://arcprize.org/arc-agi/3>)
  * Review the [ARC-AGI-3 scoring methodology](<https://docs.arcprize.org/methodology>)
  * Browse related work 
    * [VISTA: A Visual Harness For Reasoning in an Interactive World](<https://vista-research.github.io/>)
    * [Tycho: Active Abstraction with Programmatic World Models for ARC-AGI-3](<https://arxiv.org/abs/2607.28287>)

_Editor’s note: We updated the wording to more precisely distinguish the ARC-AGI-3 public set from the semi-private and private competition sets._
