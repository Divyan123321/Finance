from flask import Flask, request, session, render_template, redirect, jsonify
from cs50 import SQL
from werkzeug.security import check_password_hash, generate_password_hash
import yfinance as yf
from flask_socketio import SocketIO, emit



app = Flask(__name__)
app.secret_key="yoitsme"

socketio=SocketIO(app, cors_allowed_origins="*")

db = SQL("sqlite:///finance.db")

live_stocks=["AAPL", "TSLA", "GOOG", "MSFT", "AMZN", "NVDA", "META", "NFLX", "BABA", "DIS",
             "ORCL", "IBM", "INTC", "ADBE", "PYPL", "SHOP", "SQ", "UBER", "LYFT", "ZM"]

latest_prices={s:"N/A" for s in live_stocks}
stock_names={}
_poller_started=False

#background flag so we dont start multiple pollers

def price_poller():
    # Backgorund loop which fetches latest prices for live_stocks and emit them
    import time
    global latest_prices, stock_names

    while True:
        try:
            tickers = yf.Tickers(" ".join(live_stocks))
            for symbol, ticker in tickers.tickers.items():
                try:
                    p = ticker.info.get("regularMarketPrice")
                    latest_prices[symbol] = round(p, 2) if p is not None else "N/A"
                    stock_names[symbol] = ticker.info.get("longName", symbol)
                except Exception:
                    latest_prices[symbol] = "N/A"
                    stock_names[symbol] = symbol
        except Exception:
            # If fetching batch fails, skip this round
            pass
        socketio.emit("price_update", latest_prices)
        socketio.sleep(6)


@socketio.on("connect")
def _on_connect():
    global _poller_started

    if not _poller_started:
        socketio.start_background_task(price_poller)
        _poller_started=True



@app.route("/")
def landing():
    return render_template("home.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    user_id=session["user_id"]
    
    stock_data=[]
    for symbol in live_stocks:
            stock_data.append({
                "symbol":symbol,
                "name":stock_names.get(symbol, symbol),
                "price": latest_prices.get(symbol, "N/A")
            })

            #getting the username
    user=db.execute("SELECT username FROM users WHERE id=?", user_id)
    if user:
        username=user[0]["username"]
    else:
        username=("user")
        
    #Portfolio dashboard
    portfolio=db.execute("SELECT * FROM holdings WHERE user_id=?", user_id)

    #Watchlist dashboard
    raw_watch=db.execute("SELECT * FROM watchlist WHERE user_id=?", user_id)
    watchlist=[]
    for r in raw_watch:
        sym=r["symbol"]
        
        watchlist.append({"symbol":sym,
                           "name":stock_names.get(sym, sym),
                             "price":latest_prices.get(sym, "N/A")})
         
    u=db.execute("SELECT username FROM users WHERE id=?", user_id)
    username=u[0]["username"] if u else "User"

    cash_row=db.execute("SELECT cash FROM users WHERE id=?", user_id)
    cash_balance=cash_row[0]["cash"] if cash_row else 0.0


    return render_template("dashboard.html", username=username, stocks=stock_data,
                            portfolio=portfolio, watchlist=watchlist, cash_balance=cash_balance )



@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method=="POST":
        username=request.form.get("username")
        password=request.form.get("password")

        if not username or not password:
            return render_template("login.html", error="must provide username and password correctly")
        
        user=db.execute("SELECT * FROM users WHERE username=?", username)
        #if the login gets unsucessfull
        if len(user)!=1 or not check_password_hash(user[0]["hash"], password):
            return render_template("login.html", error="invalid username or password")
        
        #its for when login gets successfull
        session["user_id"]=user[0]["id"]
        return redirect("/dashboard")
    #the upcoming lien si for rendering the page when the user in the home page clicks on login as a get call  
    return render_template("login.html")

#the register page backend code is heeeere

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method=="POST":
        username=request.form.get("username")
        password=request.form.get("password")
        confirmation=request.form.get("confirmation")

        if not username or not password or not confirmation:
            return render_template("register.html",error="Ha! Ha! Naughty boy")
        if confirmation!=password:
            return render_template("register.html", error="Oops! Looks like you entered the wrong confirmation")
        
        existing_user=db.execute("SELECT * FROM users WHERE username=?",username)
        if len(existing_user)!=0:
            return render_template("register.html", error="Whoa! Someone beat you to that username!")
        #now we are adding users here in the else file kinda
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",username, generate_password_hash(password))

        return redirect("/login")
    return render_template("register.html")

#here comes the logout route
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

#the search stocks code is present here
@app.route("/search_stocks", methods=["GET", "POST"])
def search_stocks():
    if request.method=="POST":
        query=request.form.get("query").strip()
        if not query:
            return render_template("search.html",error=("Enter a ticker or a company name"))

        try:
            ticker=yf.Ticker(query)
            price=ticker.info.get("regularMarketPrice", "N/A")
            name=ticker.info.get("longName",query)
            return render_template("search.html", symbol=query.upper(), name=name, price=price,)
        except:
            return render_template("search.html", error="Stock not found or invalid ticker")  

    return render_template("search.html") 

@app.route("/trade/<symbol>", methods=["GET", "POST"])
def trade(symbol):
    if "user_id" not in session:
        return redirect("/login")
    
    user_id=session["user_id"]

    try:
        ticker=yf.Ticker(symbol)
        price=ticker.info.get("regularMarketPrice", "N/A")
        name=ticker.info.get("longName",symbol) 
    except:
        price="N/A"
        name=symbol

    if request.method=="POST":
        quantity=request.form.get("quantity")
        action=request.form.get("action")

        #validate input
        try:
            quantity=int(quantity)
            if quantity<=0:
                return render_template("trade.html", name=name, symbol=symbol, price=price, error="Quantity must be positive")
        except:
            return render_template("trade.html", name=name, symbol=symbol, price=price , error="Invalid response")
        
        #fetching user cash and current hldings
        user=db.execute("SELECT cash FROM users WHERE id=?", user_id)
        user_cash=user[0]["cash"]

        holding=db.execute("SELECT shares, avg_price FROM holdings WHERE user_id=? AND symbol=?", user_id, symbol)
        current_shares=holding[0]["shares"] if holding else 0
        avg_price=holding[0]["avg_price"] if holding else 0

        #buy logic
        if action=="buy":
            total_cost=quantity*price
            if user_cash<total_cost:
                return render_template("trade.html", name=name, symbol=symbol, price=price, error="You do not have enough cash")
            
            #update o insert holdings

            if holding:
                new_shares=current_shares + quantity
                new_avg=((current_shares*avg_price)+total_cost)/new_shares
                db.execute("UPDATE holdings SET shares=?, avg_price=? WHERE user_id=? AND symbol=?", new_shares, new_avg, user_id,symbol)
            else:
                db.execute("INSERT INTO holdings(user_id,symbol,shares,avg_price) VALUES (?,?,?,?)",user_id, symbol, quantity, price)

            
            #update user cash

            new_cash=user_cash - total_cost
            db.execute("UPDATE users SET cash=? WHERE id=?",new_cash, user_id)

            #record_transaction
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, ?)",user_id,symbol,quantity,price,"buy")
            return render_template("trade.html",symbol=symbol,name=name, price=price, success=f"Bought {quantity} of {symbol}")
        
        #sell logic will be here

        elif action=="sell":
            if current_shares<quantity:
                return render_template("trade.html", symbol=symbol, price=price, name=name, error="Hey, you have less shares for {symbol} than you ar trying to buy")
        
            total_gain=quantity*price
            new_shares=current_shares-quantity

            if new_shares==0:
                db.execute("DELETE FROM holdings WHERE user_id=? AND symbol=?",user_id, symbol)
            else:
                db.execute("UPDATE holdings SET shares=? WHERE user_id=? AND symbol=?",new_shares, user_id, symbol)

            new_cash = user_cash + total_gain
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, ?)",user_id, symbol, quantity, price, "sell")
            
            return render_template("trade.html", symbol=symbol, name=name, price=price, success=f"Sold {quantity} shares of {symbol}")

        else:
            return render_template("trade.html", symbol=symbol, name=name, price=price, error="Invalid action")


    return render_template("trade.html", symbol=symbol, name=name, price=price)

@app.route("/add_watchlist", methods=["POST"])
def add_watchlist():
    if "user_id" not in session:
        return redirect("/login")
    
    user_id=session["user_id"]
    symbol=request.form.get("symbol")

    if not symbol:
        return redirect("/dashboard")
    
    # prevent duplicates
    existing=db.execute("SELECT * FROM watchlist WHERE user_id=? AND symbol=?", user_id, symbol)
    if existing:
        return redirect("/dashboard")
    
    db.execute("INSERT INTO watchlist (user_id, symbol) VALUES (?,?)", user_id, symbol)
    return redirect("/dashboard")


@app.route("/remove_watchlist", methods=["POST"])
def remove_watchlist():
    if "user_id" not in session:
        return redirect("/login")
    
    user_id=session["user_id"]

    symbol=request.form.get("symbol")

    db.execute("DELETE FROM watchlist where user_id=? AND symbol=?", user_id, symbol)
    return redirect("/dashboard")




@app.route("/dashboard/chart_data/<symbol>")
def chart_data(symbol):
    try:
        ticker=yf.Ticker(symbol)
        hist=ticker.history(period="1mo", interval="1d")
        chart_labels=[str(date.date()) for date in hist.index]
        chart_prices=[round(price, 2) for price in hist["Close"]]
        return jsonify({"labels":chart_labels, "prices":chart_prices, "symbol": symbol})
    except:
        return jsonify({"error": "Failed to fetch chart data"}), 400

    


if __name__ == "__main__":
    socketio.run(app,  debug=True)


    
    
    
    
    




