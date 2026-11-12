<p>
  <a href="https://github.com/nishant-Tiwari24/cracked">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./assets/logo-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="./assets/logo-light.svg">
      <img alt="cracked" src="./assets/logo-light.svg" width="369">
    </picture>
  </a>
</p>

# Skills For Getting Hired

[![GitHub stars](https://img.shields.io/github/stars/nishant-Tiwari24/cracked?style=flat&color=c6ff3d&labelColor=0c0c0e&logo=github)](https://github.com/nishant-Tiwari24/cracked/stargazers)
[![Release](https://img.shields.io/github/v/release/nishant-Tiwari24/cracked?color=c6ff3d&labelColor=0c0c0e)](https://github.com/nishant-Tiwari24/cracked/releases)
[![Validate](https://github.com/nishant-Tiwari24/cracked/actions/workflows/validate.yml/badge.svg)](https://github.com/nishant-Tiwari24/cracked/actions/workflows/validate.yml)
[![Skills](https://img.shields.io/badge/skills-19-c6ff3d?labelColor=0c0c0e)](#reference)
[![Companies](https://img.shields.io/badge/companies-470%2B-c6ff3d?labelColor=0c0c0e)](./skills/core/company-intel/SKILL.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-c6ff3d?labelColor=0c0c0e)](LICENSE)

Agent skills for tech placements and coding interviews. Straight from your terminal.

**[cracked-skills.vercel.app](https://cracked-skills.vercel.app)**: browse every skill, and search 470+ companies' most-asked questions.

**cracked** turns Claude Code, Codex, Cursor, GitHub Copilot or Gemini CLI into your **interviewer, coach and career team**: company-wise mock DSA interviews for Google, Amazon, Microsoft, Flipkart and 470+ more; timed online assessments graded against hidden test cases; system design and HR rounds; a brutal resume roast with an ATS score; and a prep plan built from your real weak spots.

**Built for** final-year and pre-final-year CS students preparing for campus placements, new grads applying off-campus, and engineers switching jobs.

<p align="center">
  <img src="./assets/demos/mock-interview.svg" alt="Example cracked mock interview: a dynamic programming problem where the interviewer answers a greedy idea with a counterexample, the code is tested against 20,000 random inputs, a follow-up is asked, and the round ends with a Hire 8/10 scorecard." width="900">
</p>

Preparing for tech interviews is hard. Sheets, courses and grind lists try to help by handing you a list of 450 problems. But a list doesn't interview you, doesn't tell you *why* you'd be rejected, and has no idea which company you're walking into on Monday.

These skills are small, composable and honest. They work with any model. They run your code instead of guessing about it. They never invent a single fact about you. Hack around with them. Make them your own.

## Installation (30-second setup)

A plugin updates itself. [skills.sh](https://skills.sh) copies editable files into your setup, and you update them by hand. Pick one per agent, because installing both gives you every skill twice.

### 1. Get the skills

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude plugin marketplace add nishant-Tiwari24/cracked
claude plugin install cracked@cracked
```

Updates itself by default.

</details>

<details>
<summary><strong>Codex</strong></summary>

```bash
codex plugin marketplace add nishant-Tiwari24/cracked
codex plugin add cracked@cracked
```

</details>

<details>
<summary><strong>Any other agent, or editable files</strong> (manual updates)</summary>

```bash
npx skills@latest add nishant-Tiwari24/cracked -a <agent>  # cursor, copilot, gemini, opencode, windsurf, amp…; omit -a to choose
```

When the installer asks which skills to take, include `setup-cracked` and `cracked-profile`. To update, run `npx skills@latest update`.

</details>

<details>
<summary><strong>Using cracked in agents without a Skill tool</strong></summary>

Skills hand off to each other ("Call the Skill tool with `company-intel`"). Claude Code and Codex do this natively. In other agents, the skills tell the model to open the named skill's `SKILL.md` and follow it, so install the whole pack, not single skills, and always include `cracked-profile`.

</details>

### 2. Run `/setup-cracked`

Run it once. It will:

- Ask up to six short questions (status, target roles, target companies, language, DSA level, deadline) and save your profile
- Build a prep brief for each target company
- Check your machine for the tools some skills use (Python, SQLite, `gh`, text-to-speech)
- Suggest your first three sessions

### 3. Bam, you're ready to go.

```text
> roast my resume ~/Downloads/resume.pdf
> mock interview for Google, medium, voice mode
> /oa-sim Amazon
```

## Why These Skills Exist

I built these skills to fix the ways interview prep fails the people doing it.

### #1: Practice Doesn't Feel Like The Real Thing

> "Everybody has a plan until they get punched in the mouth."
>
> Mike Tyson

**The Problem**: You solve a problem alone, with the editorial one click away and no clock. Then, in the real round, someone withholds the constraints, asks "can you do better?", and watches you go quiet for six minutes.

**The Fix** is an interviewer that behaves like one:

- [`/mock-interview`](./skills/interview/mock-interview/SKILL.md): a timed DSA round. It withholds constraints so you learn to ask, gives a 4-rung hint ladder instead of answers, **runs your code against hidden edge cases**, monitors how you react at every phase, and checks that the work is yours. Turn on **voice mode** to explain out loud, the skill most people never practise.
- [`/oa-sim`](./skills/interview/oa-sim/SKILL.md): a full online assessment as real files in your own editor, graded AC / WA / TLE against hidden tests whose expected outputs come from an **executed** reference solution.
- [`/system-design-mock`](./skills/interview/system-design-mock/SKILL.md) and [`/hr-round`](./skills/interview/hr-round/SKILL.md): the other rounds, with real pushback.

<img src="./assets/demos/oa-sim.svg" alt="Example /oa-sim run: a Google-style test graded against hidden tests, with failure patterns explained and a cutoff verdict." width="900">

### #2: You're Preparing For "An Interview", Not *The* Interview

> "If you know the enemy and know yourself, you need not fear the result of a hundred battles."
>
> Sun Tzu, The Art of War

**The Problem**: Google, Amazon, a mass recruiter and a seed-stage startup run completely different interviews. Generic prep treats them all the same.

**The Fix** is **company mode**. Name a company anywhere ("Flipkart OA", "HR round for Amazon") and every skill adapts.

- [`/company-intel`](./skills/core/company-intel/SKILL.md) builds a cached brief: reported rounds and OA format, **the company's most frequently reported LeetCode questions** (30-day, 3-month, 6-month and all-time windows, 470+ companies), published values, and the resume bar, each with its source.
- [`/resume-blueprint`](./skills/profile/resume-blueprint/SKILL.md) tells you what *your* resume should contain for that company.

No company named? Everything still works, in a generic product-company style.

<img src="./assets/demos/company-intel.svg" alt="Real /company-intel output: Amazon's topic mix and most reported medium and hard questions from the last 30 days." width="900">

### #3: Your Resume Says Nothing

> "Be so good they can't ignore you."
>
> Steve Martin

**The Problem**: "Worked on a website." "Responsible for backend." "Hardworking team player." Recruiters give it six seconds, and those bullets spend them saying nothing.

**The Fix**:

- [`/roast-my-resume`](./skills/profile/roast-my-resume/SKILL.md): brutal, but **calibrated to your level and market**, with an ATS score out of 100 and its breakdown. Every jab comes with a fix, and rewrites **never invent a metric**: missing numbers become `[N]`, and you get asked for the real ones.
- [`/jd-match`](./skills/profile/jd-match/SKILL.md): a transparent match score against a real job description, with the gaps sorted into fix-today, learn-in-7-days, and can't-close.
- [`/defend-my-project`](./skills/interview/defend-my-project/SKILL.md): reads your project's actual code and cross-examines you on it, quoting `file:line`, the way a sharp interviewer does.
- [`/make-it-hireable`](./skills/profile/make-it-hireable/SKILL.md) and [`/github-glowup`](./skills/profile/github-glowup/SKILL.md): turn the college project and the empty GitHub into proof.

<img src="./assets/demos/roast-my-resume.svg" alt="Example /roast-my-resume run: ATS score breakdown, quoted weak bullets with fixes, rewrites with [N] placeholders and a verdict." width="900">

<details>
<summary>See <code>/github-glowup</code> in action</summary>

<img src="./assets/demos/github-glowup.svg" alt="Example /github-glowup run: recruiter view, a leaked secret caught, pinned-repo issues, README styles and the applied changes." width="900">

And the profile README it can build, with your photo turned into braille ASCII (Style E):

<img src="./assets/demos/github-glowup-readme.svg" alt="Example: /github-glowup builds a neofetch-style profile README for dave1725, with the avatar converted to a braille ASCII portrait next to real profile facts." width="900">

</details>

### #4: Nobody Tells You Why You Failed

> "Pain + Reflection = Progress"
>
> Ray Dalio, Principles

**The Problem**: Rejected, again. So you grind more random problems, and fail the same way, because the real failure mode was never named.

**The Fix** is a memory. Every session ends with a scorecard logged to a local journal (`~/.cracked/`), tagged with your weak spots:

```
cracked · /mock-interview · 2026-11-06
Find a Free Slot (medium)

Verdict: Lean Hire  (7/10)

Problem Solving        ████████░░  8
Correctness & Testing  ██████░░░░  6
Communication          ████████░░  8
Complexity Analysis    ███████░░░  7

Strongest: Asked about overlapping and touching intervals before coding.
Fix next:  You said "done" before testing. Trace two edge cases out loud first.
Trend: 5 → 6 → 7 over your last 3 mocks.
```

- [`/rejection-review`](./skills/strategy/rejection-review/SKILL.md) reconstructs the rounds, finds the root cause, checks your journal for the same failure repeating, and prescribes three drills.
- [`/prep-plan`](./skills/strategy/prep-plan/SKILL.md) builds the week-by-week plan from your deadline, your hours, your target companies and **your actual weak spots**, then re-plans every time you come back.

### #5: The Last Mile Is Invisible

> "You do not rise to the level of your goals. You fall to the level of your systems."
>
> James Clear, Atomic Habits

**The Problem**: The referral you never asked for properly. The offer you accepted because "18 LPA" sounded bigger, before you spotted the ₹2 lakh bond.

**The Fix**:

- [`/referral-dm`](./skills/profile/referral-dm/SKILL.md) picks the path that works (a comment on the hiring post, a recruiter DM, alumni, warming up before the ask) and writes every message. LinkedIn notes stay under 300 characters, and nothing is fabricated.
- [`/offer-decode`](./skills/strategy/offer-decode/SKILL.md) turns CTC into real in-hand pay, with the tax math done step by step in a shell, the red flags called out, and a negotiation draft.

### Summary

Interviews reward the same fundamentals they always have: clear thinking, honest self-assessment, and deliberate practice against the real thing. These skills are my best effort at turning that into a repeatable system you can run from your terminal. Go get cracked.

## Reference

These split on one axis: who can invoke them. **User-invoked** skills run only when you type them. **Model-invoked** skills run when you type them *or* when you just describe what you want ("roast my resume") and the agent reaches for them. That's why almost everything here is model-invoked.

### Core

**User-invoked**

- **[setup-cracked](./skills/core/setup-cracked/SKILL.md)**: One-time setup: your profile, briefs for your target companies, an environment check, and your first three sessions.

**Model-invoked**

- **[company-intel](./skills/core/company-intel/SKILL.md)**: A cached prep brief for any company: reported rounds, OA format, frequently reported LeetCode questions and topics (470+ companies), values and resume bar, all sourced.
- **[cracked-profile](./skills/core/cracked-profile/SKILL.md)**: The shared memory layer: your profile, the journal, and the scorecard format. Every skill loads it first.

### Interview

**Model-invoked**

- **[mock-interview](./skills/interview/mock-interview/SKILL.md)**: A timed DSA round with company-wise questions, a hint ladder, real code execution, behaviour monitoring, voice mode, integrity checks, and a hire/no-hire verdict.
- **[oa-sim](./skills/interview/oa-sim/SKILL.md)**: A company-specific online assessment as real files, graded against hidden tests verified by an executed reference solution.
- **[pattern-coach](./skills/interview/pattern-coach/SKILL.md)**: Learn DSA patterns through Socratic questions, never answers. Ends with a pattern card and a transfer test.
- **[core-viva](./skills/interview/core-viva/SKILL.md)**: Rapid-fire OS · DBMS · CN · OOP · SQL with adaptive difficulty; SQL answers are executed in SQLite.
- **[system-design-mock](./skills/interview/system-design-mock/SKILL.md)**: HLD and LLD rounds calibrated from fresher to SDE-2, with realistic pushback.
- **[hr-round](./skills/interview/hr-round/SKILL.md)**: Behavioral answers scored on STAR, specificity and length, mapped to the company's values, and saved to a reusable story bank.
- **[defend-my-project](./skills/interview/defend-my-project/SKILL.md)**: Cross-examination on your real project code, plus a defense sheet with your pitch and prepared answers.

### Profile

**Model-invoked**

- **[roast-my-resume](./skills/profile/roast-my-resume/SKILL.md)**: A brutal, level- and market-calibrated roast with an ATS score, a recruiter scan, and fabrication-free rewrites.
- **[resume-blueprint](./skills/profile/resume-blueprint/SKILL.md)**: A company-specific resume plan and a fill-in skeleton built from your real experience.
- **[jd-match](./skills/profile/jd-match/SKILL.md)**: Resume vs job description, with a transparent score, gap triage, and a 7-day plan.
- **[github-glowup](./skills/profile/github-glowup/SKILL.md)**: A recruiter's-eye audit, a leaked-secret check, and a modern profile README in five styles, including a neofetch layout with your photo turned into ASCII art.
- **[make-it-hireable](./skills/profile/make-it-hireable/SKILL.md)**: A college project upgraded to production grade on a branch, one reviewed commit at a time.
- **[referral-dm](./skills/profile/referral-dm/SKILL.md)**: Hiring-post comments, connection notes, DMs, alumni and recruiter outreach, and follow-ups that get replies.

### Strategy

**Model-invoked**

- **[prep-plan](./skills/strategy/prep-plan/SKILL.md)**: A week-by-week plan from your deadline, target companies and journal weak spots; re-plans on every run.
- **[rejection-review](./skills/strategy/rejection-review/SKILL.md)**: An honest post-mortem: root cause, repeating patterns, three drills.
- **[offer-decode](./skills/strategy/offer-decode/SKILL.md)**: CTC → in-hand pay, red flags, offer comparison and a negotiation draft.

## Quality

Every skill ships with a behavioural eval run through Claude Code's plugin eval harness: 12 realistic candidate requests, graded by deterministic checks (did the code actually run, were the OA files created) plus LLM judges (no spoilers, no fabricated metrics, correct tax math). **12/12 pass, scoring +0.38 over the same model without the skills.** See [evals/](./evals/README.md).

## Your data

Everything lives in `~/.cracked/` on your machine (override it with `CRACKED_HOME`). It's plain Markdown you can read, edit or delete. There's no account, no server and no tracking. Company questions come from the community-maintained [leetcode-company-wise-problems](https://github.com/liquidslr/leetcode-company-wise-problems) dataset, fetched at runtime and labelled "frequently reported", never "leaked".

## Contributing

New rubrics, question banks and country-specific `/offer-decode` references are especially welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Star History

If cracked helped you prepare, a ⭐ helps the next person find it.

<a href="https://star-history.com/#nishant-Tiwari24/cracked&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=nishant-Tiwari24/cracked&type=Date&theme=dark">
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=nishant-Tiwari24/cracked&type=Date">
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=nishant-Tiwari24/cracked&type=Date" width="600">
  </picture>
</a>

## License

[MIT](LICENSE) © Nishant Tiwari
