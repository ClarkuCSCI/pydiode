import argparse
from collections import defaultdict
import csv
import logging


def get_analysis_rows(tx_file, rx_file):
    """
    Identify dropped and out of order packets.

    This script assumes each packet only shares a PacketDigest with its
    redundant copies. For this assumption to hold, random data should be
    transmitted.

    If packets are received out of order in a transfer which includes
    redundancy, it will be ambiguous which redundant packet was received. For
    out of order packets, we assume that the most recently transmitted
    redundant packet is what we received.

    :param tx_file: .csv file with details about the transmitted packets
    :param rx_file: .csv file with details about the received packets
    :returns: A list of analysis row dictionaries. Each analysis row
              corresponds to a transmitted packet.
    """
    # We haven't seen these transmitted packets yet, but we might receive them
    # out of order later. PacketDigests map to lists of SentIDs.
    saved_tx_rows = defaultdict(list)
    # A list of analysis row dictionaries. Each analysis row corresponds to a
    # transmitted packet.
    analysis_rows = []

    tx_reader = csv.DictReader(tx_file)
    rx_reader = csv.DictReader(rx_file)
    tx_row = next(tx_reader)
    rx_row = next(rx_reader)
    while tx_row and rx_row:
        if tx_row["PacketDigest"] == rx_row["PacketDigest"]:
            analysis_rows.append(
                {
                    "SentID": tx_row["ID"],
                    "Received": 1,
                    "Ordered": 1,
                }
            )
            try:
                tx_row = next(tx_reader)
            except StopIteration:
                tx_row = None
            try:
                rx_row = next(rx_reader)
            except StopIteration:
                rx_row = None
        # If we saved a matching tx packet earlier, this rx packet was
        # received out of order
        elif saved_tx_rows[rx_row["PacketDigest"]]:
            logging.info(f"Using leftover {rx_row['PacketDigest']}")
            tx_id = saved_tx_rows[rx_row["PacketDigest"]].pop()
            assert analysis_rows[int(tx_id)]["SentID"] == tx_id
            analysis_rows[int(tx_id)] = {
                "SentID": tx_id,
                "Received": 1,
                "Ordered": 0,
            }
            # The current tx_row wasn't used, so only advance rx_row
            try:
                rx_row = next(rx_reader)
            except StopIteration:
                rx_row = None
        # Save the tx packet, in case we see it later
        else:
            logging.info(f"Saving {tx_row['PacketDigest']} for later")
            saved_tx_rows[tx_row["PacketDigest"]].append(tx_row["ID"])
            # For now, assume the tx packet was not received
            analysis_rows.append(
                {
                    "SentID": tx_row["ID"],
                    "Received": 0,
                    "Ordered": 1,
                }
            )
            # Don't advance to the next rx_row until we find the
            # corresponding tx_row
            try:
                tx_row = next(tx_reader)
            except StopIteration:
                tx_row = None

    # If we ran out of rx_rows before tx_rows, then the remaining
    # tx_rows correspond to dropped packets
    while tx_row:
        analysis_rows.append(
            {
                "SentID": tx_row["ID"],
                "Received": 0,
                "Ordered": 1,
            }
        )
        try:
            tx_row = next(tx_reader)
        except StopIteration:
            tx_row = None

    # If we ran out of tx_rows before rx_rows, the remaining rx_rows must
    # correspond to out of order packets
    while rx_row:
        logging.info(f"Using leftover {rx_row['PacketDigest']}")
        tx_id = saved_tx_rows[rx_row["PacketDigest"]].pop()
        assert analysis_rows[int(tx_id)]["SentID"] == tx_id
        analysis_rows[int(tx_id)] = {
            "SentID": tx_id,
            "Received": 1,
            "Ordered": 0,
        }
        try:
            rx_row = next(rx_reader)
        except StopIteration:
            rx_row = None

    return analysis_rows


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

    with open(args.send_details, newline="") as tx_file:
        with open(args.receive_details, newline="") as rx_file:
            analysis_rows = get_analysis_rows(tx_file, rx_file)

    n_dropped = 0
    n_unordered = 0
    with open(args.analysis, "w", newline="") as out_file:
        writer = csv.DictWriter(
            out_file, fieldnames=["SentID", "Received", "Ordered"]
        )
        writer.writeheader()
        for i, analysis_row in enumerate(analysis_rows):
            assert i == int(analysis_row["SentID"])
            writer.writerow(analysis_row)
            if not analysis_row["Received"]:
                logging.info(f"sentID {analysis_row['SentID']} was dropped")
                n_dropped += 1
            elif not analysis_row["Ordered"]:
                logging.info(f"sentID {analysis_row['SentID']} was unordered")
                n_unordered += 1
            else:
                logging.debug(f"Received sentID {analysis_row['SentID']}")

    print("{:.2f}% packet loss".format(n_dropped / len(analysis_rows) * 100))
    print("{} unordered packets".format(n_unordered))


if __name__ == "__main__":
    main()
