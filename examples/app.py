import payment_core
import utils


def main():
    print("PyCloak demo checkout")
    items = [120.5, 49.9, 8.0, 299.0]
    total = payment_core.checkout(items, 0.1)
    token = utils.make_token("yg", total)
    print(utils.render(token, total))


if __name__ == "__main__":
    main()
