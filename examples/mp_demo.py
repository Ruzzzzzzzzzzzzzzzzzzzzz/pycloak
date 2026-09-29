import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor


def heavy(n):
    total = 0
    for i in range(n):
        total += i * i
    return total


def main():
    mp.freeze_support()
    with ProcessPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(heavy, [1000, 2000, 3000, 5000]))
    print("mp results:", results)
    print("mp expected:", [sum(i * i for i in range(n)) for n in [1000, 2000, 3000, 5000]])


if __name__ == "__main__":
    main()
