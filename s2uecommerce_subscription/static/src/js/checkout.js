odoo.define('s2usubscription.shoppingcard_checkout', function (require) {
    $(document).ready(function () {
        var checkoutForm = $('.checkout-data-form');

        if (checkoutForm) {
            checkoutForm.find("input[name='order_type']").each(function() {
                $(this).on('click', function (event) {
                    togglePrivateCompany('b2b-required', $(this).val());
                })
            });

            checkoutForm.find("input[name='delivery_type']").each(function() {
                $(this).on('click', function (event) {
                    toggleDeliveryAddress($(this).val());
                })
            });

            checkoutForm.find("input[name='order_delivery_type']").each(function() {
                $(this).on('click', function (event) {
                    togglePrivateCompany('b2b-delivery-required', $(this).val());
                    if ($(this).val() == 'b2b') {
                        var company = checkoutForm.find("input[name='company']").val()
                        if (company) {
                            checkoutForm.find("input[name='delivery_company']").val(company)
                        }
                    }
                })
            });

            // init form
            delivery_type = checkoutForm.find("input[name='delivery_type']:checked").val();
            toggleDeliveryAddress(delivery_type);
        }

        function togglePrivateCompany(classprefix, type) {
            if (type == 'b2b') {
                checkoutForm.find("." + classprefix + "-input").each(function() {
                    $(this).attr("required", true)
                });
                checkoutForm.find("." + classprefix).each(function() {
                    $(this).removeClass("hide");
                })
            } else {
                checkoutForm.find("." + classprefix + "-input").each(function() {
                    $(this).attr("required", false)
                });
                checkoutForm.find("." + classprefix).each(function() {
                    $(this).addClass("hide");
                })
            }
        }

        function toggleDeliveryAddress(type) {
            if (type == 'different') {
                checkoutForm.find(".delivery-required").each(function() {
                    $(this).removeClass("hide");
                });
                delivery_b2c_or_b2b = checkoutForm.find("input[name='order_delivery_type']:checked").val();
                togglePrivateCompany('b2b-delivery-required', delivery_b2c_or_b2b)
            } else {
                checkoutForm.find(".delivery-required").each(function() {
                    $(this).addClass("hide");
                })
            }
        }
    })
});
