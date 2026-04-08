from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class MyState(TypedDict, total=False):
    a: int
    b: str

def node1(state: MyState):
    return {"a": state.get("a", 0) + 1, "b": "hello"}

builder = StateGraph(MyState)
builder.add_node("node1", node1)
builder.add_edge(START, "node1")
builder.add_edge("node1", END)

graph = builder.compile()

print(graph.invoke({"a": 1}))
