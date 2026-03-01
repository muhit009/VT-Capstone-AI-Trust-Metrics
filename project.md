


GroundCheck
RAG Confidence Scoring System


"Know when to trust your AI answers."




Project DocumentationCapstone Project 2026

Team:Confidence Engine: Xuhui & MuhitBackend/RAG: Shashwat & TorrinFrontend/UI: Aneesh & Ethan

Timeline: 10-12 Weeks

Table of Contents
1. Executive Summary								3
2. Problem Statement								4
3. Solution Overview								5
4. Technical Architecture								7
5. Confidence Scoring System								9
6. User Interface								12
7. Use Cases & Examples								14
8. Project Scope								16
9. Timeline & Milestones								18
10. Team Responsibilities								19
11. Technical Stack								20
12. Validation & Success Metrics								21
13. Risks & Mitigations								22
14. Future Enhancements								23
15. Glossary								24

1. Executive Summary
Project Overview
GroundCheck is a confidence scoring system for document-based question answering. It combines Retrieval-Augmented Generation (RAG) with uncertainty quantification to tell users not just what the AI's answer is, but how much they should trust it.
The One-Line Description
A confidence scoring layer for document Q&A that tells users how trustworthy an AI answer is based on how well it's supported by the source documents.
Key Value Proposition
GroundCheck answers the critical question that standard AI systems cannot:
"Is this answer actually grounded in the documents, or is the AI making things up?"
What Users Get
AI-Generated Answer
Natural language response to their question
Confidence Score (0-100)
Quantified trustworthiness of the answer
Confidence Tier
Actionable label: HIGH / MEDIUM / LOW
Source Citations
Exact documents and passages supporting the answer
Project Scope
Single open-source LLM (Llama or Mistral) running on university HPC
Two confidence signals: Grounding Score + Generation Confidence
Three actionable tiers: High (≥70), Medium (40-69), Low (<40)
Complete end-to-end system with web dashboard
Validation on 50-100 Q&A pairs with known correct answers

2. Problem Statement
The Challenge
Organizations increasingly rely on AI systems to answer questions from their document repositories. However, these systems have a critical flaw:
AI systems give answers without indicating how reliable those answers are.
Why This Matters
Risk
Consequence
Hallucination
AI fabricates plausible-sounding but incorrect information
Misplaced Trust
Users act on unreliable answers without verification
No Accountability
Cannot trace why AI gave a particular answer
The Gap in Current Solutions
Solution
What It Does
What's Missing
Basic Search (Ctrl+F)
Finds text matches
No understanding, misses context
Standard RAG
AI answers from documents
No indication of reliability
ChatGPT + Docs
Conversational answers
May hallucinate, no confidence signal
Who Feels This Pain
Engineers who need verified specifications quickly
Program managers making decisions based on AI-assisted research
Compliance analysts who cannot afford to act on unverified information
New employees learning from large documentation sets
Anyone who asks: "Can I trust this AI answer?"
The Core Problem We Solve
Users have documents but cannot efficiently extract reliable answers from them. They need a system that provides answers AND tells them when those answers can be trusted.

3. Solution Overview
What GroundCheck Does
GroundCheck is a complete document Q&A system with built-in confidence scoring. Users can:
1. Upload Documents: Add PDFs, manuals, policies to the knowledge base
2. Ask Questions: Query in natural language
3. Get Answers: Receive AI-generated responses
4. See Confidence: View score (0-100) and tier (High/Medium/Low)
5. Verify Sources: Click through to exact supporting passages
The Key Differentiator
Unlike standard RAG systems, GroundCheck adds a "trust layer" that answers:
Is this answer grounded?
Measures how well the answer is supported by retrieved documents
How certain was the AI?
Measures the model's own confidence during generation
Should I trust this?
Combines signals into actionable tier: use it, verify it, or reject it
How It Works (Simplified)
Step 1: Document Ingestion
Documents are split into chunks and stored in a vector database with embeddings.
Step 2: Question Processing
User's question is converted to an embedding and matched against document chunks.
Step 3: Answer Generation
Top matching chunks are sent to the LLM, which generates an answer.
Step 4: Confidence Scoring
The answer is analyzed for grounding (supported by docs?) and generation confidence (was AI certain?).
Step 5: Result Presentation
User sees: Answer + Score + Tier + Citations with links to source documents.
The User Experience
Before GroundCheck: "Here's an answer. Good luck figuring out if it's right."

After GroundCheck: "Here's an answer. It's 85% confidence (HIGH) because all claims are supported by these 3 documents [click to verify]."

4. Technical Architecture
System Components
4.1 Document Layer
Input
PDF, TXT, DOCX files
Processing
Text extraction → Chunking (500 tokens with overlap)
Embedding
sentence-transformers (all-MiniLM-L6-v2)
Storage
ChromaDB vector database
Output
Searchable document chunks with metadata
4.2 Retrieval Layer
Query Embedding
Same model as document embedding for consistency
Similarity Search
Cosine similarity in vector space
Top-K Retrieval
Return top 5 most relevant chunks
Metadata
Document name, page number, chunk position
4.3 Generation Layer
Model
Llama-3.1-8B-Instruct or Mistral-7B-Instruct
Serving
Ollama (simple) or vLLM (fast)
Context
Retrieved chunks + user query
Output
Generated answer + token probabilities
4.4 Confidence Engine
Signal 1
Grounding Score (NLI-based claim verification)
Signal 2
Generation Confidence (token probability analysis)
Fusion
Weighted combination: 0.7 × Grounding + 0.3 × GenConf
Output
Final score (0-100) + Tier (High/Medium/Low)
4.5 API Layer
Framework
FastAPI with Pydantic models
Endpoints
POST /query, GET /documents, POST /upload
Response Format
JSON with answer, scores, citations
Logging
SQLite database for audit trail
4.6 Frontend Layer
Framework
React + TypeScript
Styling
Tailwind CSS
Components
Query input, Answer display, Confidence visualization, Source panel
State Management
React hooks

Architecture Diagram
System Flow:

┌─────────────────────────────────────────────────────────────────┐│                         USER INTERFACE                          ││  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ ││  │ Query Input │  │ Answer View │  │ Confidence + Citations  │ ││  └─────────────┘  └─────────────┘  └─────────────────────────┘ │└─────────────────────────────────────────────────────────────────┘                              │                              ▼┌─────────────────────────────────────────────────────────────────┐│                         API LAYER                               ││                    FastAPI + Pydantic                           │└─────────────────────────────────────────────────────────────────┘                              │          ┌───────────────────┼───────────────────┐          ▼                   ▼                   ▼┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐│   RETRIEVAL     │ │   GENERATION    │ │   CONFIDENCE ENGINE     ││                 │ │                 │ │                         ││ ChromaDB        │ │ Llama/Mistral   │ │ Grounding Score         ││ Vector Search   │ │ LLM Generation  │ │ Generation Confidence   ││ Top-K Chunks    │ │ Token Probs     │ │ Fusion Algorithm        │└─────────────────┘ └─────────────────┘ └─────────────────────────┘          │                   │                   │          └───────────────────┴───────────────────┘                              │                              ▼┌─────────────────────────────────────────────────────────────────┐│                      DOCUMENT STORE                             ││  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ ││  │ Raw Files   │  │ Chunks      │  │ Embeddings (ChromaDB)   │ ││  └─────────────┘  └─────────────┘  └─────────────────────────┘ │└─────────────────────────────────────────────────────────────────┘

5. Confidence Scoring System
5.1 Overview
The confidence scoring system evaluates AI-generated answers using two independent signals, combines them using a weighted fusion algorithm, and outputs an actionable confidence tier.
5.2 Signal 1: Grounding Score
Purpose: Measure how well the generated answer is supported by the retrieved documents.

Methodology:
1. Extract individual claims/statements from the generated answer
2. For each claim, compute semantic similarity against each retrieved chunk
3. Use NLI (Natural Language Inference) to determine if chunk entails the claim
4. Grounding Score = Average of maximum entailment scores per claim

Formula:
Grounding_Score = (1/N) × Σ max(NLI_entailment(claim_i, chunk_j))

Where:
N = number of claims in the answer
claim_i = individual claim extracted from answer
chunk_j = retrieved document chunk
NLI_entailment = probability that chunk entails claim (using DeBERTa)

Interpretation:
0.8 - 1.0
Strongly grounded: All claims supported by documents
0.5 - 0.8
Partially grounded: Most claims supported
0.2 - 0.5
Weakly grounded: Few claims supported
0.0 - 0.2
Not grounded: Claims not found in documents
5.3 Signal 2: Generation Confidence
Purpose: Measure how certain the LLM was when generating the answer.

Methodology:
1. During generation, capture token-level probabilities (logits)
2. Convert logits to probabilities using softmax
3. Calculate average (or minimum) probability across all generated tokens
4. Higher average probability = model was more certain

Formula:
Gen_Confidence = (1/T) × Σ P(token_t | context)

Where:
T = number of tokens in generated answer
P(token_t | context) = probability of token t given previous context

Why This Works:
Open-source models (Llama, Mistral) provide access to logits, unlike API-based models. When a model is uncertain, token probabilities are spread across multiple options. When confident, probability is concentrated on one token.

5.4 Fusion Algorithm
Purpose: Combine individual signals into a single confidence score.

Formula:
Final_Score = 100 × (0.7 × Grounding_Score + 0.3 × Gen_Confidence)

Weight Rationale:
Signal
Weight
Rationale
Grounding Score
70%
Primary signal for RAG — faithfulness to documents is most important
Generation Confidence
30%
Supplementary signal — catches uncertainty even when retrieval looks good
5.5 Confidence Tiers
Purpose: Convert numeric score into actionable guidance.

Tier
Score Range
Meaning
Recommended Action
HIGH
70 - 100
Answer is well-supported by documents
Safe to use with standard review
MEDIUM
40 - 69
Partial support, some uncertainty
Verify key claims before acting
LOW
0 - 39
Weak or no support from documents
Do not rely on this answer
5.6 Edge Cases
Scenario
How System Handles It
No relevant documents found
Low retrieval score → Low overall confidence → System warns user
Answer is correct but not in corpus
Low grounding score (intended behavior — we measure groundedness, not correctness)
High grounding but low generation confidence
Medium overall score — model uncertain despite good sources
Conflicting information in documents
Consistency check fails → Lower confidence → Show conflicting sources

6. User Interface
6.1 Main Dashboard
The dashboard provides a clean, intuitive interface for document Q&A with confidence scoring.
Key Components:
Knowledge Base Indicator
Shows corpus name, document count, last update — visible BEFORE querying
Query Input
Text field for natural language questions
Answer Display
AI-generated response with inline citation markers [1][2]
Confidence Panel
Score (0-100), tier badge (HIGH/MEDIUM/LOW), signal breakdown
Source Panel
List of retrieved documents with similarity scores and page references
Verification Links
Click-through to exact passages in source documents
6.2 Confidence Visualization
The confidence display uses multiple visual elements:
Numeric score (e.g., "78%") for precision
Progress bar for quick visual assessment
Color-coded tier badge: Green (HIGH), Yellow (MEDIUM), Red (LOW)
Expandable breakdown showing individual signal scores
6.3 Example Interface
┌─────────────────────────────────────────────────────────────────────┐│  GROUNDCHECK                                                        ││  ────────────────────────────────────────────────────────────────── ││  📚 Knowledge Base: Engineering_Standards_v2.3                      ││     Documents: 47 | Last Updated: Feb 15, 2026                      │├─────────────────────────────────────────────────────────────────────┤│                                                                     ││  ┌─────────────────────────────────────────────────────────────┐   ││  │ Ask a question about your documents...                       │   ││  │                                                               │   ││  │ "What is the maximum torque specification for M10 bolts      │   ││  │  in structural applications?"                         [ASK]  │   ││  └─────────────────────────────────────────────────────────────┘   ││                                                                     │├─────────────────────────────────────────────────────────────────────┤│  ANSWER                                                             ││  ───────                                                            ││  The maximum torque specification for M10 bolts in structural       ││  applications is 45 N·m (±5%) according to specification            ││  DIN-EN-ISO-898-1. This applies to property class 8.8 bolts        ││  with standard zinc coating. [1][2]                                 ││                                                                     │├─────────────────────────────────────────────────────────────────────┤│  CONFIDENCE                                                         ││  ──────────                                                         ││  ┌─────────────────────────────────────────────────────────────┐   ││  │  Score: 84%  ████████████████░░░░  [HIGH ✓]                 │   ││  │                                                               │   ││  │  ▼ Breakdown                                                  │   ││  │    • Grounding Score:     89%  (3/3 claims verified)         │   ││  │    • Generation Conf:     72%  (model reasonably certain)    │   ││  └─────────────────────────────────────────────────────────────┘   ││                                                                     │├─────────────────────────────────────────────────────────────────────┤│  SOURCES                                                            ││  ───────                                                            ││  [1] Fastener_Specifications.pdf                                    ││      Page 23, Section 4.2 | Similarity: 0.94                        ││      "M10 bolts class 8.8 shall be torqued to 45 N·m..."           ││      [View Document]                                                ││                                                                     ││  [2] Structural_Assembly_Guide.pdf                                  ││      Page 67, Table 12 | Similarity: 0.87                           ││      "Torque values for metric fasteners..."                        ││      [View Document]                                                ││                                                                     │└─────────────────────────────────────────────────────────────────────┘

7. Use Cases & Examples
7.1 Engineering Specifications Query
Scenario: An engineer needs to verify material specifications quickly.

Query: "What is the minimum yield strength for ASTM A36 steel?"

Answer
The minimum yield strength for ASTM A36 steel is 36,000 psi (250 MPa).
Confidence
91% [HIGH]
Grounding
95% — Claim directly matches source
Source
Materials_Handbook.pdf, page 12, Table 3-1
Action
Engineer can proceed with confidence
7.2 Policy Compliance Query (Low Confidence)
Scenario: A manager asks about a policy not well-covered in the corpus.

Query: "What are the overtime approval requirements for exempt employees?"

Answer
Overtime for exempt employees requires director-level approval...
Confidence
32% [LOW]
Grounding
25% — Only 1 of 4 claims found in documents
Warning
⚠️ Low confidence — Retrieved documents may not cover this topic
Action
Manager should consult HR directly, not rely on this answer
7.3 Safety Procedure Query (Medium Confidence)
Scenario: A technician needs to verify an emergency procedure.

Query: "What is the emergency shutdown procedure for the hydraulic press?"

Answer
1) Press E-Stop, 2) Close valve V-12, 3) Notify supervisor, 4) Complete incident form
Confidence
58% [MEDIUM]
Grounding
67% — Steps 1-3 verified, Step 4 not found
Recommendation
⚡ Verify step 4 with safety manual before proceeding
Action
Technician should confirm the incident form requirement
7.4 Value Demonstration
These examples show how GroundCheck helps users make informed decisions:
Confidence
User Knows
Time Saved
HIGH (91%)
Safe to proceed, answer is verified
30+ minutes of manual searching
MEDIUM (58%)
Mostly reliable, verify specific parts
20 minutes (partial verification only)
LOW (32%)
Don't trust this, find another source
Prevents costly mistakes

8. Project Scope
8.1 In Scope (What We Are Building)
Component
Details
LLM
Single open-source model: Llama-3.1-8B or Mistral-7B
RAG Pipeline
Document ingestion, embedding, retrieval, generation
Confidence Signals
2 signals: Grounding Score + Generation Confidence
Fusion Algorithm
Fixed weights (0.7 / 0.3) with research justification
Confidence Tiers
3 tiers: High (≥70), Medium (40-69), Low (<40)
Dashboard
Web UI showing answer, confidence, and citations
Logging
Basic audit trail: queries, answers, scores, timestamps
Validation
50-100 Q&A pairs with calibration analysis
8.2 Out of Scope (What We Are NOT Building)
Feature
Reason for Exclusion
Multi-model support
Complexity without core value; single model is sufficient for demo
Configurable weights UI
Fixed weights work; configurability is a stretch goal
Historical trend analysis
Requires long-term data; basic logging is sufficient
Automated feedback loops
Requires ML pipeline; manual analysis is acceptable
Risk flagging system
Additional complexity; users can interpret tiers themselves
Real-time retraining
Out of scope for 12-week project
Multi-language support
English only for MVP
8.3 Stretch Goals (If Time Permits)
User-adjustable confidence weights via UI slider
Historical confidence tracking dashboard
Automated low-confidence alerts
User feedback collection (thumbs up/down)
Comparison with second LLM for consistency
8.4 Scope Change from Original Proposal
Aspect
Original Proposal
Revised Scope
LLM Support
Model-agnostic (any LLM)
Single open-source model
Use Case
General LLM confidence
RAG document Q&A specifically
Signals
3+ signals
2 signals
Weights
User-configurable
Fixed (research-backed)
Tracking
Historical trends
Basic logging
Feedback
Automated retraining
Manual review

9. Timeline & Milestones
Phase Overview
Phase
Weeks
Focus
Key Deliverable
1: Foundation
1-3
Setup, RAG pipeline, confidence design
Working RAG system (no confidence yet)
2: Confidence Engine
4-6
Implement scoring signals and fusion
API returns answers with confidence scores
3: Dashboard
7-9
Build user interface
Complete web application
4: Validation
10-12
Testing, calibration, documentation
Final demo with validation results
Detailed Timeline
Weeks 1-3: Foundation
Define confidence model and scoring framework (Task 1.1, 1.2)
Set up document ingestion pipeline (Task 3.1)
Configure vector database (Task 3.2, 3.3)
Set up LLM serving on HPC (Task 7.1)
Milestone: Can upload docs and get AI answers
Weeks 4-6: Confidence Engine
Implement grounding score calculation (Task 2.1)
Implement generation confidence extraction (Task 2.2)
Implement fusion algorithm (Task 2.3)
Create API endpoints (Task 2.4)
Milestone: API returns answer + confidence + citations
Weeks 7-9: Dashboard
Design and implement query interface (Task 5.1, 5.2)
Build confidence visualization (Task 5.3, 5.4)
Implement source citation panel (Task 5.5)
Milestone: Complete working web application
Weeks 10-12: Validation & Polish
Create validation Q&A dataset (50-100 pairs)
Run calibration testing
Analyze results and adjust thresholds if needed
Write documentation
Prepare final demo
Milestone: Validated system ready for presentation

10. Team Responsibilities
Team
Members
Responsibilities
Confidence Engine
Xuhui & Muhit
Define confidence modelImplement grounding scoreImplement generation confidenceDesign and implement fusion algorithmCalibration and validation
Backend / RAG
Shashwat & Torrin
Document ingestion pipelineVector database setupLLM serving configurationFastAPI endpointsLogging infrastructure
Frontend / UI
Aneesh & Ethan
Dashboard designQuery interfaceConfidence visualizationSource citation panelUser experience
Cross-Team Dependencies
Confidence Engine depends on Backend for LLM outputs and token probabilities
Frontend depends on Backend for API endpoints
Frontend depends on Confidence Engine for score format and tier definitions
All teams collaborate on integration testing
11. Technical Stack
Component
Technology
Rationale
LLM
Llama-3.1-8B-Instruct
Best quality at size, good documentation
LLM Serving
Ollama or vLLM
Ollama for simplicity, vLLM for speed
Embeddings
sentence-transformers (all-MiniLM-L6-v2)
Fast, free, good quality
Vector Store
ChromaDB
Zero config, Python-native
NLI Model
DeBERTa-v3-small
Standard for entailment tasks
Backend
FastAPI
Async, auto-docs, Pydantic validation
Frontend
React + TypeScript
Team familiarity, strong ecosystem
Styling
Tailwind CSS
Rapid UI development
Database
SQLite
Simple logging, no setup
Compute
University HPC
GPU access for LLM inference
Version Control
GitHub
Team collaboration

12. Validation & Success Metrics
12.1 What We Will Measure
Metric
Definition
Target
High Tier Accuracy
% of HIGH confidence answers that are correct
≥ 80%
Low Tier Accuracy
% of LOW confidence answers that are correct
< 50%
Calibration Error (ECE)
Alignment between confidence and actual accuracy
< 0.15
Tier Separation
Difference in accuracy between HIGH and LOW tiers
≥ 30 percentage points
12.2 Validation Dataset
50-100 Q&A pairs with verified correct answers
Sourced from: advisor-provided corpus, public technical docs, or adapted benchmarks
Stratified by question type: factual, multi-step, out-of-scope
Includes questions that SHOULD get low confidence (adversarial/edge cases)
12.3 Success Criteria
Minimum Success (Pass): 
Working end-to-end system with documented validation results (even if calibration needs improvement)
Target Success (Good): 
System meets accuracy targets; HIGH tier is meaningfully more accurate than LOW tier
Stretch Success (Excellent): 
Well-calibrated system (ECE < 0.10) with compelling demo and clear real-world applicability
13. Risks & Mitigations
Risk
Likelihood
Impact
Mitigation
Grounding score doesn't correlate with correctness
Medium
High
Test early (week 4); fallback to embedding similarity
HPC queue delays
Medium
Medium
Start HPC setup in week 1; have local fallback
Integration issues between components
Medium
Medium
Define API contracts early; weekly integration tests
Validation dataset too small
Low
Medium
Start creating Q&A pairs in week 1; use public datasets
Scope creep
Medium
High
Strict adherence to MVP scope; stretch goals only after core complete

14. Future Enhancements
The following features are out of scope for the current project but represent valuable future work:
Short-Term (Next Semester)
User-adjustable confidence weights
User feedback collection and analysis
Support for additional document formats
Improved claim extraction using LLM
Medium-Term (6-12 Months)
Multi-model support (GPT-4, Claude)
Historical confidence tracking and trends
Automated drift detection and alerts
Integration with enterprise systems
Long-Term (Research Extensions)
Self-improving confidence calibration based on feedback
Domain-specific confidence models
Claim-level confidence (instead of answer-level)
Confidence for multi-modal content (images, tables)
15. Glossary
Term
Definition
Calibration
The alignment between predicted confidence and actual accuracy. A well-calibrated system is correct 80% of the time when it says 80% confidence.
Chunk
A segment of a document (typically 500 tokens) stored in the vector database for retrieval.
ECE (Expected Calibration Error)
A metric measuring how well confidence scores match actual accuracy across all predictions.
Embedding
A numerical vector representation of text that captures semantic meaning.
Fusion
The process of combining multiple confidence signals into a single score.
Generation Confidence
A measure of how certain the LLM was when generating each token of the answer.
Grounding Score
A measure of how well the generated answer is supported by the retrieved documents.
Hallucination
When an AI generates false or fabricated information not supported by its sources.
NLI (Natural Language Inference)
A task that determines if one text (premise) entails, contradicts, or is neutral to another text (hypothesis).
Q&A Pair
A question and its known correct answer, used for validation and testing.
RAG (Retrieval-Augmented Generation)
A technique that retrieves relevant documents and uses them as context for LLM generation.
Tier
A categorical label (HIGH/MEDIUM/LOW) that converts numeric confidence into actionable guidance.
Token Probability
The model's predicted probability for each word/subword it generates.
Vector Database
A database optimized for storing and searching embeddings by similarity.




GroundCheck
"Know when to trust your AI answers."


A confidence scoring system for document Q&A that tells usershow trustworthy an AI answer is based on source document support.


For questions about this project, contact the team leads.
