from flask import Flask, render_template, request
import requests
import urllib.parse

app = Flask(__name__)

class ReActAgent:
    def __init__(self):
        self.steps = []

    def think(self, text: str) -> None:
        self.steps.append({"type": "Thought", "text": text})

    def act(self, text: str) -> None:
        self.steps.append({"type": "Action", "text": text})

    def observe(self, text: str) -> None:
        self.steps.append({"type": "Observation", "text": text})

    def final_answer(self, text: str) -> None:
        self.steps.append({"type": "Final Answer", "text": text})

    def needs_search(self, question: str) -> bool:
        lower = question.lower()
        time_sensitive = ["current", "latest", "today", "now", "year", "202", "recent", "new", "update"]
        factual = ["who", "when", "where", "what", "which", "how many", "how much", "how long", "date", "price", "population", "statistic"]
        if any(token in lower for token in time_sensitive + factual):
            return True
        if len(question.split()) > 10:
            return True
        return False

    def search_web(self, query: str) -> str:
        encoded = urllib.parse.quote_plus(query)
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
            "t": "react-agent"
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return f"Search failed: {exc}"

        if data.get("AbstractText"):
            source = data.get("AbstractURL") or "DuckDuckGo"
            return f"{data['AbstractText']} (Source: {source})"

        related = []
        for item in data.get("RelatedTopics", []):
            if isinstance(item, dict) and item.get("Text"):
                related.append(item["Text"])
                if len(related) >= 3:
                    break

        if related:
            return " | ".join(related)

        return "No strong evidence was found in the search results."

    def answer(self, question: str) -> dict:
        self.steps = []
        self.think("Analyze the question to determine whether a grounded web search is needed.")

        if self.needs_search(question):
            self.think("This query appears to require factual or time-sensitive evidence, so execute a Search action.")
            self.act(f"Search[{question}]")
            observation = self.search_web(question)
            self.observe(observation)
            self.think("Assess whether the observation provides sufficient evidence to answer the question.")

            if "No strong evidence" in observation or observation.startswith("Search failed"):
                self.think("The first search result is insufficient. If the question is ambiguous, refine the query and search again.")
                refined = question + " facts"
                self.act(f"Search[{refined}]")
                observation = self.search_web(refined)
                self.observe(observation)
                self.think("Use the best available evidence to produce a grounded answer.")

            if observation.startswith("Search failed"):
                final_text = "I could not retrieve grounded evidence from the web search."
            elif observation == "No strong evidence was found in the search results.":
                final_text = "The query could not be answered with strong grounded evidence from search results."
            else:
                final_text = (
                    f"Based on the search evidence, the answer is: {observation}"
                )
        else:
            self.think("The question appears general enough to answer with reasoning without an external search.")
            self.act("Final Answer")
            final_text = (
                "This agent is configured to use web search for factual or time-sensitive questions. "
                "For general conceptual queries, it can provide concise reasoning directly."
            )

        self.final_answer(final_text)
        return {
            "question": question,
            "steps": self.steps,
        }

agent = ReActAgent()

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            result = agent.answer(question)
    return render_template("index.html", result=result)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8501)
