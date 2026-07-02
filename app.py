from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

games_db = {}
game_counter = 0


class SudokuGenerator:
    def __init__(self):
        self.symbols = {
            6: ['1', '2', '3', '4', '5', '6'],
            9: ['1', '2', '3', '4', '5', '6', '7', '8', '9'],
            16: ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F']
        }

    def generate_solution(self, n):
        grid = [[0] * n for _ in range(n)]
        numbers = list(range(1, n + 1))

        def solve(grid):
            for row in range(n):
                for col in range(n):
                    if grid[row][col] == 0:
                        shuffled = numbers.copy()
                        random.shuffle(shuffled)
                        for num in shuffled:
                            if self.is_valid(grid, row, col, num, n):
                                grid[row][col] = num
                                if solve(grid):
                                    return True
                                grid[row][col] = 0
                        return False
            return True

        solve(grid)
        return grid

    def is_valid(self, grid, row, col, num, n):
        for i in range(n):
            if grid[row][i] == num:
                return False
        for i in range(n):
            if grid[i][col] == num:
                return False

        if n == 6:
            block_rows, block_cols = 2, 3
        elif n == 9:
            block_rows, block_cols = 3, 3
        else:  # 16x16
            block_rows, block_cols = 4, 4

        start_row = (row // block_rows) * block_rows
        start_col = (col // block_cols) * block_cols
        for i in range(start_row, start_row + block_rows):
            for j in range(start_col, start_col + block_cols):
                if grid[i][j] == num:
                    return False
        return True

    def create_puzzle(self, solution, n, difficulty):
        puzzle = [row[:] for row in solution]

        remove_percent = {
            'easy': 0.30,
            'medium': 0.45,
            'hard': 0.55,
            'expert': 0.65
        }.get(difficulty, 0.40)

        cells_to_remove = int(n * n * remove_percent)
        removed = 0
        while removed < cells_to_remove:
            row = random.randint(0, n - 1)
            col = random.randint(0, n - 1)
            if puzzle[row][col] != 0:
                puzzle[row][col] = 0
                removed += 1
        return puzzle

    def get_symbols(self, n):
        return self.symbols.get(n, self.symbols[9])


generator = SudokuGenerator()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/generate', methods=['POST'])
def generate_puzzle():
    global game_counter
    try:
        data = request.json
        size = data.get('size', 9)
        difficulty = data.get('difficulty', 'medium')

        solution = generator.generate_solution(size)
        puzzle = generator.create_puzzle(solution, size, difficulty)
        symbols = generator.get_symbols(size)

        game_counter += 1
        game_id = game_counter
        games_db[game_id] = {
            'id': game_id,
            'puzzle': puzzle,
            'solution': solution,
            'size': size,
            'difficulty': difficulty,
            'symbols': symbols,
            'created_at': datetime.now().isoformat()
        }
        return jsonify({
            'game_id': game_id,
            'puzzle': puzzle,
            'solution': solution,
            'size': size,
            'difficulty': difficulty,
            'symbols': symbols
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/validate', methods=['POST'])
def validate_move():
    try:
        data = request.json
        row = data.get('row')
        col = data.get('col')
        value = data.get('value')
        solution = data.get('solution')
        if row is None or col is None or value is None:
            return jsonify({'error': 'Missing fields'}), 400
        is_valid = solution[row][col] == value
        return jsonify({'valid': is_valid, 'correct_value': solution[row][col]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save', methods=['POST'])
def save_game():
    try:
        data = request.json
        game_id = data.get('game_id')
        current_state = data.get('current_state')
        mistakes = data.get('mistakes', 0)
        hints_used = data.get('hints_used', 0)
        time_spent = data.get('time_spent', 0)
        if game_id not in games_db:
            return jsonify({'error': 'Game not found'}), 404
        games_db[game_id]['current_state'] = current_state
        games_db[game_id]['mistakes'] = mistakes
        games_db[game_id]['hints_used'] = hints_used
        games_db[game_id]['time_spent'] = time_spent
        return jsonify({'game_id': game_id, 'message': 'Game saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load/<int:game_id>', methods=['GET'])
def load_game(game_id):
    try:
        if game_id not in games_db:
            return jsonify({'error': 'Game not found'}), 404
        return jsonify(games_db[game_id])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        recent_games = []
        for game_id in sorted(games_db.keys(), reverse=True)[:5]:
            game = games_db[game_id]
            recent_games.append({
                'id': game_id,
                'size': game['size'],
                'difficulty': game['difficulty'],
                'created_at': game.get('created_at', ''),
                'mistakes': game.get('mistakes', 0)
            })
        return jsonify({'total_games': len(games_db), 'recent_games': recent_games})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/hint', methods=['POST'])
def get_hint():
    try:
        data = request.json
        game_id = data.get('game_id')
        row = data.get('row')
        col = data.get('col')
        if game_id not in games_db:
            return jsonify({'error': 'Game not found'}), 404
        game = games_db[game_id]
        solution = game['solution']
        if row is None or col is None:
            for r in range(len(solution)):
                for c in range(len(solution)):
                    if game['puzzle'][r][c] == 0:
                        row, col = r, c
                        break
                if row is not None:
                    break
        if row is None or col is None:
            return jsonify({'error': 'No empty cells'}), 400
        value = solution[row][col]
        symbols = generator.get_symbols(game['size'])
        return jsonify({'row': row, 'col': col, 'value': value, 'symbol': symbols[value - 1]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'games': len(games_db), 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    print("=" * 50)
    print("🧩 СУДОКУ СЕРВЕР ЗАПУЩЕН!")
    print("📍 http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000) 