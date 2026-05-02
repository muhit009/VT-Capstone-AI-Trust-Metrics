# FAQ

## General Questions

### What is the Boeing Aircraft Assistant?
The Boeing Aircraft Assistant is a chat-based AI tool that helps Boeing new hires ask airplane-related questions and review the trustworthiness of the answers through confidence, evidence, explanation, and metadata.

### Who is this application for?
It is intended for Boeing new hires and users who want grounded aircraft-related answers instead of a plain chatbot response.

### What kinds of questions work best?
The application works best for focused questions about:
- aircraft family comparisons
- performance tradeoffs
- mission profiles
- engineering terms
- source verification

### What makes this different from a normal chatbot?
This application includes a trust-review workflow. It provides answers, but also provides:
- confidence summary
- signal breakdown
- retrieved evidence
- response explanation
- request metadata

---

## Chat and Usage Questions

### How do I ask a question?
Go to the Chat page, type your question into the input box at the bottom of the screen, and click **Ask**.

### What kinds of prompts work best?
Prompts work best when they are:
- focused
- specific
- about one main topic at a time

### Why should I include assumptions in comparison questions?
Comparisons such as fuel efficiency or payload-range tradeoffs often depend on:
- mission length
- payload
- aircraft use case
- operating assumptions

Including these details usually leads to a more useful answer

### What does New chat do?
The **New chat** button clears the current conversation so the user can start a fresh interaction.

### Why does the conversation history use placeholder names?
The finalized product keeps the current structure and layout, which includes placeholder conversation names in the sidebar. These names preserve the conversation-history format even though the labels are generic.

---

## Confidence Questions

### What does High confidence mean?
High confidence means the answer appears grounded enough to reuse, although important details should still be verified.

### What does Medium confidence mean?
Medium confidence means the answer may be useful as a draft or learning aid, but the user should still check assumptions and evidence before relying on it.

### What does Low confidence mean?
Low confidence means the answer should be treated as unsafe until confirmed using supporting material.

### Can I trust an answer just because it has a confidence score?
No. The confidence score is a guide, not proof. Users should still inspect evidence and explanation before reusing the answer.

### Why did I get a warning even though the answer sounded good?
A response can sound fluent but still be only partially supported. The system may detect:
- incomplete evidence
- partial claim support
- uncertain generation behavior
- assumptions that weaken the answer

---

## Signal Breakdown Questions

### What is the Signal breakdown?
The Signal breakdown shows the internal trust-related metrics that help produce the final confidence score.

### Why would I use the Signal breakdown?
Use it when you want to understand why the confidence score is High, Medium, or Low.

### What might appear in the Signal breakdown?
Depending on the response, it may include:
- grounding score
- generation confidence
- supported claims
- claim support rate
- grounding contribution
- generation contribution
- number of citations

### What if I do not understand the metrics?
Use the Response explanation section. It is meant to summarize the trust result in more human-readable language.

---

## Evidence Questions

### What is Retrieved evidence?
Retrieved evidence is the set of supporting source materials the system used when generating the answer.

### What kinds of information are shown for a source?
A source may include:
- document name
- section
- page number
- revision
- excerpt
- retrieval score

### If a citation is shown, does that prove the answer is correct?
No. The citation helps support review, but the user still needs to check whether it truly supports the specific claim.

### Why is evidence important?
Evidence helps the user verify:
- where the answer came from
- whether the answer is grounded
- whether the answer should be trusted

---

## Response Explanation Questions

### What is the Response explanation section?
It is a plain-language explanation of why the assistant received its current confidence level.

### When should I read it?
Read it when:
- the raw metrics are too technical
- you want a quick summary of the confidence result
- you need help deciding whether the answer is safe to reuse

### Why is it useful?
It translates technical trust signals into a more readable explanation for the user.

---

## Metadata Questions

### What is Request metadata?
Request metadata includes technical details about the response, such as:
- request ID
- timestamp
- model information
- retriever information
- latency breakdown

### Do I need Request metadata to use the app?
Not usually; it is more useful for debugging, demos, and technical inspection than for ordinary use.

---

## Settings Questions

### What is the Settings page for?
The Settings page is for basic account and authentication management.

### What can I do in Settings?
In the finalized product, Settings should be used for:
- password changes
- authentication/account-related information
- related account-security actions

### Can I use Settings to change the model or backend?
No. The user-facing Settings page is not intended for advanced system configuration such as model selection or backend routing.

### Why is Settings limited?
The project is designed so that advanced backend behavior is not exposed through normal user settings. The Settings page is intended to remain simple and account-focused.

---

## Troubleshooting Questions

### Why did I get a request failure or 404?
A request failure or 404 usually indicates a backend connectivity or route issue. It means the frontend opened successfully, but the system could not complete the query request correctly.

### Why does the app open but no answer appears?
Possible causes include:
- backend not running
- route mismatch
- network/configuration issue
- server-side failure

### Why is the right panel empty?
If the answer does not return properly, the review panel may not populate. The right panel depends on a valid response object.

### Why does the answer appear but some trust sections are incomplete?
Possible causes include:
- incomplete backend response data
- missing citations
- partial response support
- weak retrieval results

### Why does the New chat button not seem to work?
In the finalized product, New chat should clear the current conversation state. If it does not, that would indicate a problem with the reset behavior.

---

## Responsible Use Questions

### Should I rely on this tool for critical engineering facts without checking anything else?
No. Even strong answers should still be reviewed when the information matters.

### What should I do before reusing an answer?
Before reusing an answer, check:
1. confidence summary
2. warnings
3. retrieved evidence
4. response explanation

### What is the safest way to use the application?
Use it as:
- a learning tool
- a drafting tool
- a structured starting point
- a way to identify supporting sources

DO NOT use it as a substitute for checking important claims.

---

## Final Reminder

The safest workflow is:
- ask a focused question
- read the answer
- review confidence
- inspect evidence
- use the explanation section
- verify important details before reuse