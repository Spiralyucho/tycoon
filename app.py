from flask import Flask, render_template, request, jsonify
import random, time

app = Flask(__name__)

# ===== 상수 =====
AUTO_INTERVAL = 10
SETTLE_INTERVAL = 180
SPY_ESCALATE_INTERVAL = 30
BASE_SPY_LOSS = 0.05
SPY_MAX_LEVEL = 5
STAFF_EFFECT = 5
INVEST_MULT = 0.1  # 투자 수익 배율

# ===== 게임 상태 =====
state = {
    "money": 100,
    "reputation": 0,
    "rep_exp": 0,
    "auto_level": 0,
    "staff": 0,
    "security": 0,
    "invested": 0,

    "last_auto": time.time(),
    "last_settle": time.time(),
    "money_at_settle": 100,

    "spy_active": False,
    "spy_level": 0,
    "last_spy_tick": time.time(),
    "internal_suspect": None,
    "spy_hint": "",

    "logs": [],
    "spy_logs": [],
    "income_history": []
}

# ===== 평판 =====
def rep_need(rep): return 5 + rep*3
def gain_rep(amount):
    state["rep_exp"] += amount
    while state["rep_exp"] >= rep_need(state["reputation"]):
        state["rep_exp"] -= rep_need(state["reputation"])
        state["reputation"] += 1
        state["logs"].append("📈 평판 상승")
def rep_bonus(): return 1 + state["reputation"]*0.05

# ===== 보안 =====
def security_reduction(): return min(0.2*state["security"],0.5)

# ===== 자동 수익 =====
def process_auto_income():
    now = time.time()
    ticks = int((now - state["last_auto"]) // AUTO_INTERVAL)
    if ticks>0:
        income = ticks*(state["auto_level"]*10 + state["staff"]*STAFF_EFFECT + int(state["invested"]*INVEST_MULT))
        state["money"] += income
        state["last_auto"] += ticks*AUTO_INTERVAL
        if income>0:
            state["logs"].append(f"💰 자동 수익 +{income}")

# ===== 3분 정산 =====
def process_settle():
    now = time.time()
    if now - state["last_settle"] >= SETTLE_INTERVAL:
        profit = state["money"] - state["money_at_settle"]
        state["income_history"].append(profit)
        state["money_at_settle"] = state["money"]
        state["last_settle"] += SETTLE_INTERVAL
        state["logs"].append(f"📊 3분 정산 수익: {profit}")

# ===== 스파이 발생 =====
def try_start_spy():
    if state["spy_active"]: return
    if state["reputation"]>=5 and random.random()<0.15:
        state["spy_active"] = True
        state["spy_level"] = 0
        state["last_spy_tick"] = time.time()
        state["internal_suspect"] = random.choice(["직원A","직원B","직원C"])
        # 난이도 높은 추리: 힌트 랜덤화
        hints = ["평판 상승 시 행동", "투자에 관심", "직원 회의 자주 불참"]
        state["spy_hint"] = random.choice(hints)
        msg = f"🚨 스파이 침투! 내부 의심자 중 1명. 단서: {state['spy_hint']}"
        state["spy_logs"].append(msg)
        state["logs"].append(msg)

# ===== 스파이 누적 =====
def process_spy_escalation():
    if not state["spy_active"]: return
    if time.time() - state["last_spy_tick"] >= SPY_ESCALATE_INTERVAL:
        state["spy_level"] = min(state["spy_level"] + 1, SPY_MAX_LEVEL)
        state["last_spy_tick"] = time.time()
        msg = f"⚠️ 스파이 활동 심화 (위험도 {state['spy_level']})"
        state["spy_logs"].append(msg)
        state["logs"].append(msg)

# ===== 스파이 피해 =====
def process_spy_damage():
    if not state["spy_active"]: return
    reduction = security_reduction()
    loss_rate = (BASE_SPY_LOSS + state["spy_level"]*0.03)*(1 - reduction)
    loss = int(state["money"]*loss_rate)
    state["money"] -= loss
    rep_loss = 1 + state["spy_level"]//2
    state["reputation"] = max(0,state["reputation"]-rep_loss)
    msg = f"⚠️ [스파이 피해] -{loss}원 / 평판 -{rep_loss}"
    state["spy_logs"].append(msg)
    state["logs"].append(msg)

# ===== 게임틱 =====
def tick():
    process_auto_income()
    process_settle()
    try_start_spy()
    process_spy_escalation()
    process_spy_damage()

# ===== 라우트 =====
@app.route("/")
def index(): return render_template("index.html")

@app.route("/state")
def get_state():
    tick()
    return jsonify(state)

@app.route("/action", methods=["POST"])
def action():
    tick()
    a = request.json["action"]

    if a=="work":
        earn = int(random.randint(20,40)*rep_bonus())
        state["money"] += earn
        gain_rep(2)
        state["logs"].append(f"🧾 장사 수익 +{earn}")

    elif a=="upgrade":
        cost = (state["auto_level"]+1)*100
        if state["money"]>=cost:
            state["money"] -= cost
            state["auto_level"] += 1
            state["logs"].append("⚙ 자동 수익 업그레이드")

    elif a=="reputation":
        if state["money"]>=30:
            state["money"] -= 30
            gain_rep(4)
            state["logs"].append("🤝 평판 관리 활동")

    elif a=="hire_staff":
        if state["money"]>=150 and state["reputation"]>=3:
            state["money"] -= 150
            state["staff"] += 1
            state["logs"].append("👥 직원 고용")

    elif a=="hire_security":
        if state["money"]>=200:
            state["money"] -= 200
            state["security"] += 1
            state["logs"].append("🛡 보안 요원 고용")

    elif a=="investigate_spy":
        if state["money"]>=100 and state["spy_active"]:
            state["money"] -= 100
            state["spy_level"] = max(0,state["spy_level"]-1)
            state["logs"].append("🔍 스파이 활동 일부 억제")

    elif a=="purge_spy":
        if state["money"]>=300 and state["security"]>=2 and state["spy_active"]:
            state["money"] -= 300
            state["spy_active"] = False
            state["spy_level"] = 0
            state["logs"].append("🛡 스파이 완전 제거")

    elif a=="invest_money":
        invest_amt = min(200,state["money"])
        if invest_amt>0:
            state["money"] -= invest_amt
            state["invested"] += invest_amt
            state["logs"].append(f"💹 투자 완료: {invest_amt}원")

    return jsonify(state)

# ===== 추리 선택 =====
@app.route("/suspect", methods=["POST"])
def suspect():
    tick()
    guess = request.json["guess"]
    if not state["spy_active"]:
        return jsonify({"result":"스파이가 없습니다!"})
    correct = state["internal_suspect"]
    if guess == correct:
        state["spy_active"] = False
        state["spy_level"] = 0
        state["logs"].append(f"🕵️ 내부 배신자 {guess}를 찾아 스파이를 완전히 제거했습니다!")
        state["internal_suspect"] = None
        result = "정답! 스파이를 제거했습니다."
    else:
        penalty_money = int(state["money"]*0.15)  # 페널티 증가
        state["money"] -= penalty_money
        state["reputation"] = max(0,state["reputation"]-1)
        state["logs"].append(f"❌ {guess}는 배신자가 아닙니다. 자금 -{penalty_money}, 평판 -1")
        result = f"틀렸습니다. {guess}는 배신자가 아닙니다."
    return jsonify({"result":result,"money":state["money"],"reputation":state["reputation"]})

if __name__=="__main__":
    app.run(debug=True)

