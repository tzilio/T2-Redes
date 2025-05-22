import json, random, socket, sys, time
from ring_network import *          # NODES e setup_socket

# Ordem de exibição: ranks 2 - A, naipes: copas, espadas, ouros, paus
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♥", "♠", "♦", "♣"]
RANK_INDEX = {r: i for i, r in enumerate(RANKS)}
SUIT_INDEX = {s: i for i, s in enumerate(SUITS)}

# Estado global simples
hand: list[str] = []
token_sent  = [False]
pass_done   = [False]
received_from = [False]
received_pass: list[str] = []
NEXT_ADDR   = None

current_trick: list[tuple[int, str]] = []
round_number = [0]
starter_id   = [None]
player_points = [0, 0, 0, 0]


# ---------- utilidades locais ---------- #
def sort_hand(cards):
    return sorted(cards, key=lambda c: (SUIT_INDEX[c[-1]], RANK_INDEX[c[:-1]]))

def print_hand(cards):
    cols = [f"{c:>3}" for c in cards]
    idxs = [f"{i:>3}" for i in range(len(cards))]
    print("   " + " ".join(cols))
    print("   " + " ".join(idxs))

def count_points(trick):
    pts = 0
    for _, card in trick:
        if card[-1] == "♥":
            pts += 1
        elif card == "Q♠":
            pts += 13
    return pts

def print_trick_state(trick):
    state = ['--'] * 4
    for pid, card in trick:
        state[pid] = card
    print("Cartas na trick: [ " + " | ".join(state) + " ]")

def banner(text: str, char: str = "-"):
    print("\n" + char * 40)
    print(f"{text}")
    print(char * 40)

# ---------- fase DEAL ---------- #
def deal_cards(sock):
    deck = [rank + suit for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    for pid in range(4):
        packet = {
            "type": "DEAL",
            "origin": 0,
            "target": pid,
            "cards": deck[pid*13:(pid+1)*13]
        }
        sock.sendto(json.dumps(packet).encode(), NEXT_ADDR)


def handle_deal(pkt, node_id, sock):
    global hand
    if pkt["target"] == node_id:
        hand[:] = pkt["cards"]
        banner(f"[Node {node_id}] MÃO INICIAL (DEAL)")
        print_hand(sort_hand(hand))

    if pkt["origin"] != node_id:
        sock.sendto(json.dumps(pkt).encode(), NEXT_ADDR)
    elif node_id == 0 and not token_sent[0]:
        tok = {"type": "TOKEN", "phase": "pass"}
        sock.sendto(json.dumps(tok).encode(), NODES[0])
        token_sent[0] = True


# ---------- fase PASS ---------- #
def choose_cards_to_pass():
    ordered = sort_hand(hand)
    print("\nEscolha 3 cartas p/ passar (ex.: 0 4 8):")
    print_hand(ordered)
    while True:
        try:
            idxs = list(map(int, input("> ").split()))
            if len(idxs) == 3 and all(0 <= i < len(ordered) for i in idxs):
                sel = [ordered[i] for i in idxs]
                for card in sel:
                    hand.remove(card)
                print("Você vai passar:", sel)
                return sel
        except ValueError:
            pass
        print("Entrada inválida — tente de novo.")


def handle_pass(pkt, node_id, sock):
    global received_pass
    if pkt["to"] == node_id:
        received_pass = pkt["cards"]
        received_from[0] = True

        if not pass_done[0]:
            sel = choose_cards_to_pass()
            nxt = (node_id + 1) % 4
            new_pkt = {"type": "PASS", "from": node_id,
                       "to": nxt, "cards": sel}
            sock.sendto(json.dumps(new_pkt).encode(), NEXT_ADDR)
            pass_done[0] = True

        if pass_done[0] and received_from[0]:
            print(f"\n[Node {node_id}] Recebeu do jogador {pkt['from']}: {received_pass}")
            hand.extend(received_pass)

            if node_id == 3:
                sh = {"type": "SHOW_HAND", "origin": node_id}
                sock.sendto(json.dumps(sh).encode(), NEXT_ADDR)
    else:
        sock.sendto(json.dumps(pkt).encode(), NEXT_ADDR)


# ---------- mostrar mãos e iniciar jogo ---------- #
def handle_show_hand(pkt, node_id, sock):
    banner(f"[Node {node_id}] MÃO APÓS PASS")
    print_hand(sort_hand(hand))

    if pkt["origin"] != node_id:
        sock.sendto(json.dumps(pkt).encode(), NEXT_ADDR)

    if "2♣" in hand:
        starter_id[0] = node_id

        starter_pkt = {"type": "STARTER", "player": node_id, "origin": node_id}
        sock.sendto(json.dumps(starter_pkt).encode(), NEXT_ADDR)
        time.sleep(0.1)

        tok = {"type": "TOKEN", "phase": "play",
               "starter": node_id, "round": 1, "trick": []}
        sock.sendto(json.dumps(tok).encode(), NEXT_ADDR)


def handle_starter(pkt, node_id, sock):
    banner(f"Jogador {pkt['player']} começa a 1ª rodada (2♣)", "=")
    if pkt["origin"] != node_id:
        sock.sendto(json.dumps(pkt).encode(), NEXT_ADDR)


# ---------- fase PLAY ---------- #
def choose_play():
    print("\nSua vez de jogar — índice da carta:")
    ordered = sort_hand(hand)
    print_hand(ordered)
    while True:
        try:
            idx = int(input("> "))
            if 0 <= idx < len(ordered):
                return ordered[idx]
        except ValueError:
            pass
        print("Índice inválido.")

def determine_trick_winner(trick):
    lead_suit = trick[0][1][-1]
    same_suit = [(pid, card) for pid, card in trick if card[-1] == lead_suit]
    return max(same_suit, key=lambda x: RANK_INDEX[x[1][:-1]])[0]

def handle_token(pkt, node_id, sock):
    phase = pkt.get("phase")

    # -------- PASS -------- #
    if phase == "pass" and not pass_done[0]:
        sel = choose_cards_to_pass()
        to = (node_id + 1) % 4
        p = {"type": "PASS", "from": node_id, "to": to, "cards": sel}
        sock.sendto(json.dumps(p).encode(), NEXT_ADDR)
        pass_done[0] = True

    # -------- PLAY -------- #
    elif phase == "play":
        starter_id[0]   = pkt["starter"]
        round_number[0] = pkt["round"]
        trick           = pkt["trick"]

        print_trick_state(trick)

        if len(trick) < 4:
            if (starter_id[0] + len(trick)) % 4 == node_id:
                card = choose_play()
                hand.remove(card)
                trick.append((node_id, card))
                print(f"[Node {node_id}] Jogou {card}")
                print_trick_state(trick)

            pkt["trick"] = trick
            sock.sendto(json.dumps(pkt).encode(), NEXT_ADDR)

        else:
            winner = determine_trick_winner(trick)
            pts    = count_points(trick)
            player_points[winner] += pts

            summary = {
                "type": "ROUND_SUMMARY",
                "starter": starter_id[0],
                "trick": trick,
                "winner": winner,
                "add_points": pts,
                "points": player_points.copy(),
                "origin": node_id,
                "round": round_number[0],
            }
            sock.sendto(json.dumps(summary).encode(), NEXT_ADDR)

            if round_number[0] == 13:
                game_over = {"type": "GAME_OVER",
                             "points": player_points.copy(),
                             "origin": node_id}
                time.sleep(0.5)
                sock.sendto(json.dumps(game_over).encode(), NEXT_ADDR)
            else:
                next_tok = {"type": "TOKEN", "phase": "play",
                            "starter": winner,
                            "round": round_number[0] + 1,
                            "trick": []}
                time.sleep(0.5)
                sock.sendto(json.dumps(next_tok).encode(), NEXT_ADDR)


def handle_round_summary(pkt, node_id, sock):
    player_points[:] = pkt["points"]
    r = pkt["round"]
    banner(f"Fim da rodada {r}")
    print(f"Jogador que começou: {pkt['starter']}")
    for pid, card in pkt["trick"]:
        print(f"  Jogador {pid} jogou {card}")
    print(f"Vencedor da rodada: Jogador {pkt['winner']}  (+{pkt['add_points']} pts)")
    print("Pontuação parcial:", player_points)

    if pkt["origin"] != node_id:
        sock.sendto(json.dumps(pkt).encode(), NEXT_ADDR)


# ---------- fim de jogo ---------- #
def handle_game_over(pkt, node_id, sock):
    pts = pkt["points"]
    winner = min(range(4), key=lambda p: pts[p])
    banner("FIM DE JOGO", "#")
    for pid, p in enumerate(pts):
        print(f"Jogador {pid}: {p} pontos")
    print(f"\n*** Vencedor: Jogador {winner} (menor pontuação) ***\n")

    if pkt["origin"] != node_id:
        sock.sendto(json.dumps(pkt).encode(), NEXT_ADDR)

    if pkt["origin"] == node_id:
        time.sleep(0.5)
        bye = {"type": "EXIT"}
        sock.sendto(json.dumps(bye).encode(), NEXT_ADDR)


def handle_exit(node_id, data, sock):
    sock.sendto(data, NEXT_ADDR)
    print(f"[Node {node_id}] Encerrando processo.")
    return True


# ---------- loop principal ---------- #
def main():
    global NEXT_ADDR
    if len(sys.argv) != 2:
        print(f"Uso: {sys.argv[0]} <node_id 0-3>")
        sys.exit(1)

    node_id = int(sys.argv[1])
    if not 0 <= node_id < 4:
        print("node_id deve ser 0,1,2 ou 3")
        sys.exit(1)

    local_addr = NODES[node_id]
    NEXT_ADDR  = NODES[(node_id + 1) % 4]
    sock = setup_socket(local_addr)
    banner(f"Node {node_id} online — próximo → {NEXT_ADDR}")

    if node_id == 0:
        time.sleep(1)
        deal_cards(sock)

    while True:
        data, _ = sock.recvfrom(8192)
        try:
            pkt = json.loads(data.decode())
        except json.JSONDecodeError:
            continue

        t = pkt.get("type")
        if t == "DEAL":
            handle_deal(pkt, node_id, sock)
        elif t == "PASS":
            handle_pass(pkt, node_id, sock)
        elif t == "SHOW_HAND":
            handle_show_hand(pkt, node_id, sock)
        elif t == "STARTER":
            handle_starter(pkt, node_id, sock)
        elif t == "TOKEN":
            handle_token(pkt, node_id, sock)
        elif t == "ROUND_SUMMARY":
            handle_round_summary(pkt, node_id, sock)
        elif t == "GAME_OVER":
            handle_game_over(pkt, node_id, sock)
        elif t == "EXIT":
            if handle_exit(node_id, data, sock):
                break
        else:
            sock.sendto(data, NEXT_ADDR)

    sock.close()

if __name__ == "__main__":
    main()
