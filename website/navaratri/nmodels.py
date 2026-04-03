# nmodels.py

def create_customer(
    name,
    mobile,
    address="",
    deposit="",
    group="",
    reference="",
    bookings=None,
    given_price=0,
    total_price=0
):
    return {
        "Name": name,
        "mobile": mobile,
        "address": address,
        "deposit": deposit,
        "group": group,
        "reference": reference,
        "bookings": bookings or {},
        "given_price": given_price,
        "total_price": total_price
    }