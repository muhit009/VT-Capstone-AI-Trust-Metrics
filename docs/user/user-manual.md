# User Manual

## 1. Introduction

### Purpose
The Boeing Aircraft Assistant is a chat-based question-and-answer application designed to help Boeing new hires learn aircraft concepts, terminology, tradeoffs, and comparisons. In addition to generating answers, the system provides confidence and evidence information to help users evaluate whether a response is safe to trust and reuse.

### Intended audience
This application is intended for:
- Boeing new hires
- student evaluators and demo reviewers
- users who need grounded aircraft-related answers with supporting review information

### What makes this application different
Unlike a standard chatbot, this system is designed as both:
- an answer-generation tool, and
- an answer-review tool

Each response can be reviewed through confidence, signals, evidence, explanation, and metadata so the user can make a more informed judgment about the output.

---

## 2. Application layout

The application is organized into three main sections.

### Left sidebar
The left sidebar contains:
- the Boeing Aircraft Assistant title and branding
- the **New Analysis** button
- the main navigation options:
  - **Chat**
  - **Settings**
- a conversation history list

The conversation list is populated by saved or recent conversation slots in the interface.

### Main chat workspace
The center of the screen is the main workspace. It includes:
- the conversation between the user and the assistant
- the text input field at the bottom of the page
- the **New chat** button
- the **Ask** button

This is where users enter questions and read answers.

### Right review panel
The right side of the screen contains the review panel. This panel is used to inspect the answer more carefully. It includes:
- **Confidence summary**
- **Signal breakdown**
- **Retrieved evidence**
- **Response explanation**
- **Request metadata**
- **Confidence guide**

Together, these sections help the user understand not just the answer itself, but how much trust to place in it.

---

## 3. Getting started

To begin using the application:

1. Open the application in the browser.
2. Make sure you are on the **Chat** page.
3. Click in the text box at the bottom of the workspace.
4. Type a question.
5. Click **Ask** or press **Enter**.

After submitting the question:
- your question will appear in the conversation
- the assistant’s answer will appear beneath it
- the right review panel will populate with trust-related information for that response

---

## 4. Asking good questions

The application works best when the user asks:
- focused questions
- specific technical questions
- one main/primary question at a time

### Good question examples
Examples of effective questions include:
- What is the difference between the 737 MAX and 787 in typical mission profile?
- When comparing fuel efficiency across aircraft, what variables need to be normalized?
- Explain ETOPS in simple terms for a new engineer
- How should I compare payload-range tradeoffs between narrowbody and widebody aircraft?

### Best practices for prompting
For best results:
- use the aircraft family name when possible
- keep the question focused on one main topic
- include assumptions when asking comparison questions
- be clear about what kind of explanation you want

For example, when asking about fuel efficiency, it is better to specify whether you care about:
- mission length
- payload
- passenger assumptions
- aircraft use case

This usually leads to more meaningful and reviewable answers.

---

## 5. Using the chat workspace

### Entering a question
The chat input box is located at the bottom of the main workspace. Type your question into the box and submit it using:
- **Ask**
- or the **Enter** key

### Reading the conversation
The conversation area displays:
- the user’s prompt
- the assistant’s answer

Each answer is treated as a response that can be reviewed in more detail through the right panel.

### Starting over
Use the **New chat** button to clear the current conversation and begin a fresh session.

When New chat is used, the interface should reset the current working conversation so the user can start again without the previous answer remaining in view.

### Conversation history
The sidebar displays conversation names representing recent or saved chat entries.

---

## 6. Understanding the assistant answer

The assistant answer appears in the main chat workspace after the user submits a question.

### What the answer card provides
The answer area may include:
- the main response text
- a confidence badge or score
- source chips or evidence markers
- warning text if the answer requires extra caution

### How to use the answer area
Before reusing or relying on the answer, the user should:
1. read the response itself
2. inspect the confidence summary
3. check whether evidence is present
4. review the response explanation if needed

The answer should not be treated as automatically reliable simply because it appears fluent or detailed.

---

## 7. Understanding the confidence summary

The **Confidence summary** is the quickest way to evaluate whether the system considers the current answer trustworthy.

It typically presents:
- a score
- a confidence tier
- warning text, if needed

### Confidence levels

#### High
A high-confidence answer is grounded enough to reuse, although important facts should still be verified before being used in a formal setting.

#### Medium
A medium-confidence answer is often useful as a draft or learning aid, but it should be checked carefully against evidence and assumptions before being trusted.

#### Low
A low-confidence answer should be treated as unsafe until confirmed through supporting documents or other trusted material.

### How to interpret the score
The score is meant to act as a review aid, not as absolute proof of correctness. The user should always combine:
- the confidence score
- the evidence
- the response explanation

before deciding whether to reuse the answer.

---

## 8. Understanding the signal breakdown

The **Signal breakdown** section provides a more detailed view of the metrics that contribute to the final confidence result.

Depending on the current response, this section may include information such as:
- grounding score
- generation confidence
- supported claims
- claim support rate
- grounding contribution
- generation contribution
- evidence count

### Why this section matters
This section helps explain why a response received its current confidence level.

### Example interpretation
A response may receive medium confidence if:
- some claims are supported, but not all
- the model appears moderately confident
- the evidence exists, but is not strong enough to justify a higher confidence rating

The Signal breakdown is useful when the user wants a more technical explanation of the score.

---

## 9. Understanding retrieved evidence

The Retrieved evidence section shows the supporting source material used by the system when generating the answer.

This section may include:
- source title
- section
- page number
- revision
- excerpt text
- retrieval score

### Why evidence matters
Evidence helps the user answer an important question:
> Where did this answer come from?

### How to use evidence
Users should inspect the evidence when they want to:
- verify a claim
- understand the basis of a comparison
- decide whether an answer is safe to rely on

### Important note
The existence of evidence does not automatically prove the answer is correct. The user should still check whether the cited material actually supports the specific statement being made.

---

## 10. Understanding the response explanation

The Response explanation section gives a human-readable description of why the answer received its current confidence level.

This section is designed to make the trust result easier to understand without requiring the user to interpret every technical metric directly.

### What the explanation may describe
It may summarize:
- how much of the answer was supported
- whether the model appeared confident or uncertain
- whether warnings were present
- why the answer should be treated as High, Medium, or Low confidence

### When to use it
This section is especially useful when:
- the Signal breakdown feels too technical
- the user wants a quick explanation of the trust result
- the user is deciding whether to reuse the answer

---

## 11. Understanding request metadata

The Request metadata section contains technical details about the current response.

This may include:
- request ID
- timestamp
- model information
- retriever information
- latency breakdown

### Why metadata is useful
Metadata is helpful for:
- evaluation
- debugging
- demos
- comparing system behavior across runs

For most ordinary users, confidence, evidence, and explanation are more important than metadata.

---

## 12. Understanding the confidence guide

At the bottom of the right review panel, the Confidence guide acts as a quick reference key.

It summarizes how the system’s confidence levels should be interpreted:
- **High** = grounded enough to reuse, while still verifying critical details
- **Medium** = useful as a draft, but assumptions and evidence should be checked
- **Low** = unsafe until confirmed from source documents

The confidence guide should be used as a reminder whenever the user is uncertain how much trust to place in the answer.

---

## 13. Using the Settings page

The Settings page is intended to support basic user account and authentication management.

In the finalized product, Settings should be treated as a place to manage:
- password change
- account authentication information
- related account-security actions

### What Settings are not for
The Settings page is not intended to expose advanced system behavior such as:
- model switching
- backend target selection
- retrieval configuration
- trust-metric tuning

Those controls are outside the intended scope of the user-facing product.

---

## 14. Recommended workflow

A recommended workflow for using the application is:

1. Ask a focused question.
2. Read the assistant answer.
3. Check the confidence summary.
4. Review the signal breakdown if needed.
5. Inspect the retrieved evidence.
6. Read the response explanation.
7. Decide whether the answer is:
   - safe to reuse,
   - useful as a draft only,
   - or unsafe until verified.

This is the intended use pattern of the system.

---

## 15. Best practices

### Do
- ask focused aircraft-related questions
- include assumptions for comparison-based prompts
- inspect evidence before repeating claims
- use the confidence guide when judging trust
- treat medium-confidence responses as draft-quality unless verified

### Don't
- assume a polished answer is automatically correct
- reuse low-confidence answers without checking the source material
- ignore warning text
- treat the app as a substitute for verification on important claims

---

## 16. Known limitations

Users should understand that:
- confidence is a guide, not a guarantee
- evidence may vary in strength across responses
- some questions may still require external verification
- metadata is useful for inspection, but not all users need it
- conversation history names may still appear as placeholders in the current interface structure

---

## 17. Summary

The Boeing Aircraft Assistant is intended to be used as both:
- a question-answering tool, and
- a trust-review tool

The assistant answer, confidence summary, signal breakdown, evidence, explanation, and confidence guide should be used together when deciding whether an answer is safe to trust.