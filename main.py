from dotenv import load_dotenv
from langchain import hub
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain_core.tools import Tool, StructuredTool
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import sqlite3
import os
import re
from wikipedia import summary, exceptions

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(minutes=30)
bcrypt = Bcrypt(app)
CORS(app, supports_credentials=True)

DB_NAME = "chatbot_users.db"

# Initialize the database
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)
        conn.commit()

init_db()

# Wikipedia search tool
def search_wikipedia(query: str):
    try:
        sanitized_query = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
        return summary(sanitized_query, sentences=2)
    except exceptions.DisambiguationError as e:
        return f"Multiple results found: {str(e)}"
    except exceptions.PageError:
        return "No results found on Wikipedia."
    except Exception as e:
        return f"Error: {str(e)}"

# Time tool
def get_current_time():
    est_offset = timedelta(hours=-5)
    est_timezone = timezone(est_offset)
    now = datetime.now(est_timezone)
    return now.strftime("%Y-%m-%d %I:%M %p")

time_tool = StructuredTool.from_function(
    func=get_current_time,
    name="Time",
    description="Provides the current time in EST timezone."
)

# Tools list
tools = [Tool(
        name="Wikipedia",
        func=search_wikipedia,
        description="Useful for when you need to know information about a topic.",
    ), time_tool]

# Load the structured-chat-agent prompt
prompt = hub.pull("hwchase17/structured-chat-agent")

# ChatGPT setup
llm = ChatOpenAI(model="gpt-4o")

# Memory to maintain conversation history
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    return_messages=True,
    k=5
)

# Create the primary structured chat agent
agent = create_structured_chat_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tools,
    verbose=True,
    memory=memory,
    handle_parsing_errors=True,
    max_iterations=20,
)

# Function to invoke the agent
def get_chat_response(user_input):
    """
    Handle user input through the LangChain agent. If the agent stops due to iteration or time limits,
    fallback to ChatGPT.

    Args:
        user_input (str): User's input query.

    Returns:
        str: The response from the agent or ChatGPT (fallback).
    """
    try:
        # Add user input to memory
        memory.chat_memory.add_message(HumanMessage(content=user_input))
        print(f"User Input Added to Memory: {user_input}")

        # Try invoking the agent
        try:
            response = agent_executor.invoke({"input": user_input})

            # Check if the agent's response is valid and not an iteration limit message
            if response and "output" in response:
                if "iteration limit" in response["output"].lower():
                    print("Iteration limit reached. Falling back to ChatGPT.")
                    raise ValueError("Iteration limit reached.")
                print(f"Agent Response: {response['output']}")
                memory.chat_memory.add_message(AIMessage(content=response["output"]))
                return response["output"]

        except Exception as e:
            print(f"Agent stopped or failed: {str(e)}")

        # Fallback to ChatGPT if no valid response
        print("Fallback to ChatGPT triggered.")
        fallback_response = llm.predict(f"Provide an answer to: {user_input}")
        memory.chat_memory.add_message(AIMessage(content=fallback_response))
        return fallback_response

    except Exception as e:
        print(f"Error during agent execution or fallback: {str(e)}")
        return "Sorry, I encountered an error while processing your request."




# Flask routes
@app.route("/")
def index():
    if not session.get("initialized"):
        session.clear()
        session["initialized"] = True
    if "username" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

        if user and bcrypt.check_password_hash(user[0], password):
            session.permanent = True
            session["username"] = username
            return redirect(url_for("chat"))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
                conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username already exists")
    return render_template("register.html")

@app.route("/chat", methods=["GET"])
def chat():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html")

@app.route("/chat", methods=["POST"])
def chat_api():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        user_input = request.get_json().get("input")
        if not user_input:
            return jsonify({"error": "No input provided"}), 400

        # Get response using the agent with fallback
        response = get_chat_response(user_input)
        return jsonify({"response": response})
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.route("/current_time", methods=["GET"])
def current_time():
    """Route to get the current time."""
    try:
        time = get_current_time()  # Use the existing function to get current time
        return jsonify({"current_time": time})
    except Exception as e:
        print(f"Error in /current_time route: {str(e)}")
        return jsonify({"error": "Unable to fetch the current time"}), 500

@app.route("/view_db", methods=["GET"])
def view_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            # Query data from the 'users' table
            cursor.execute("SELECT * FROM users;")
            rows = cursor.fetchall()
            return jsonify({"users": rows})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8125)
