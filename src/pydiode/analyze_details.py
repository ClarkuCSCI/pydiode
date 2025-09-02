import argparse
import csv
import logging


def main():
    parser = argparse.ArgumentParser(
        description="pydiode packet loss analysis."
    )
    parser.add_argument(
        "send_details", help=".csv containing details of sent packets"
    )
    parser.add_argument(
        "receive_details", help=".csv containing details of received packets"
    )
    parser.add_argument(
        "analysis", help="Output .csv file for packet loss analysis"
    )
    parser.add_argument(
        "--debug",
        help="Print DEBUG logging",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        "--verbose",
        help="Print INFO logging",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    n_tx_packets = 0
    n_rx_packets = 0

    with open(args.send_details, newline="") as tx_file:
        with open(args.receive_details, newline="") as rx_file:
            with open(args.analysis, "w", newline="") as out_file:
                tx_reader = csv.DictReader(tx_file)
                rx_reader = csv.DictReader(rx_file)
                writer = csv.DictWriter(
                    out_file, fieldnames=["SentID", "Received"]
                )
                writer.writeheader()
                for rx_row in rx_reader:
                    n_rx_packets += 1
                    tx_row = next(tx_reader)
                    n_tx_packets += 1
                    while rx_row["PacketDigest"] != tx_row["PacketDigest"]:
                        writer.writerow({"SentID": tx_row["ID"], "Received": 0})
                        logging.info(f"Did not receive sentID {tx_row['ID']}")
                        tx_row = next(tx_reader)
                        n_tx_packets += 1
                    writer.writerow({"SentID": tx_row["ID"], "Received": 1})
                    logging.debug(f"Received sentID {tx_row['ID']}")

    print("{:.2f}% packet loss".format((1 - n_rx_packets / n_tx_packets) * 100))


if __name__ == "__main__":
    main()
