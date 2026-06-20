# Witness Credibility Multi-Agent System

## Install

pip install -r requirements.txt

cp .env.example .env


## Run

python main.py


## Architecture

Statements
├── Timeline Agent
├── Attribute Agent
│
Timeline
↓
Timeline Contradiction Agent

Attributes + Timeline
↓
Behavioral Consistency Agent

Contradictions + Behavior
↓
Reliability Evidence Agent

Reliability
↓
Credibility Agent