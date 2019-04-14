odoo.define('s2uecommerce.shoppingcard', function (require) {
    $(document).ready(function () {
        var cartWrapper = $('.cd-cart-container');
        var shopFilter = $('.cd-shop-filter');

        //product id - you don't need a counter in your real project but you can use your real product id
        var productId = 0;

        if (cartWrapper.length > 0) {
            //store jQuery objects
            var cartBody = cartWrapper.find('.body')
            var cartList = cartBody.find('ul').eq(0);
            var cartTotal = cartWrapper.find('.checkout').find('span');
            var cartTrigger = cartWrapper.children('.cd-cart-trigger');
            var cartCount = cartTrigger.children('.count')
            var addToCartBtn = $('.cd-add-to-cart');
            var checkoutBtn = $('.checkout');
            var undo = cartWrapper.find('.undo');
            var undoTimeoutId;

            //add product to cart
            addToCartBtn.on('click', function (event) {
                event.preventDefault();
                addToCart($(this));
                synchronizeCart();
            });

            //go to checkout
            checkoutBtn.on('click', function (event) {
                event.preventDefault();

                var mapForm = $('<form id="mapform" action="/shop/checkout" method="post"></form>');
                var fldno = 0;

                mapForm.append('<input type="hidden" name="csrf_token" value="' + require('web.core').csrf_token + '"/>');
                cartList.children('li:not(.deleted)').each(function () {
                    var singleQuantity = Number($(this).find('.quantity').find('select').val());
                    var price = singleQuantity * Number($(this).find('.price').data('price'));
                    var product_id = Number($(this).find('.price').data('productid'));
                    var product_model = $(this).find('.price').data('productmodel');
                    fldno += 1;
                    mapForm.append('<input type="hidden" name="qty_'+ fldno + '" id="qty_' + fldno + '" value="' + String(singleQuantity) + '" />');
                    mapForm.append('<input type="hidden" name="product_'+ fldno + '" id="product_' + fldno + '" value="' + String(product_id) + '" />');
                    mapForm.append('<input type="hidden" name="price_'+ fldno + '" id="price_' + fldno + '" value="' + String(price) + '" />');
                    mapForm.append('<input type="hidden" name="model_'+ fldno + '" id="model_' + fldno + '" value="' + product_model + '" />');
                });
                mapForm.append('<input type="hidden" name="items" id="items" value="' + String(fldno) + '" />');
                $('body').append(mapForm);
                mapForm.submit();
            });

            //open/close cart
            cartTrigger.on('click', function (event) {
                event.preventDefault();
                toggleCart();
            });

            //close cart when clicking on the .cd-cart-container::before (bg layer)
            cartWrapper.on('click', function (event) {
                if ($(event.target).is($(this))) toggleCart(true);
            });

            //delete an item from the cart
            cartList.on('click', '.delete-item', function (event) {
                event.preventDefault();
                removeProduct($(event.target).parents('.product'));
                synchronizeCart();
            });

            //update item quantity
            cartList.on('change', 'select', function (event) {
                quickUpdateCart();
                synchronizeCart();
            });

            //re-insert item deleted from the cart
            undo.on('click', 'a', function (event) {
                clearInterval(undoTimeoutId);
                event.preventDefault();
                cartList.find('.deleted').addClass('undo-deleted').one('webkitAnimationEnd oanimationend msAnimationEnd animationend', function () {
                    $(this).off('webkitAnimationEnd oanimationend msAnimationEnd animationend').removeClass('deleted undo-deleted').removeAttr('style');
                    quickUpdateCart();
                });
                undo.removeClass('visible');
                synchronizeCart();
            });

            var quantity = 0;
            cartList.children('li:not(.deleted)').each(function () {
                var singleQuantity = Number($(this).find('.quantity').find('select').val());
                var price = singleQuantity * Number($(this).find('.price').data('price'));
                quantity += singleQuantity;
                productId += 1;
                updateCartTotal(price, true);
            });

            if (productId) {
                updateCartCount(true, quantity);
                cartWrapper.removeClass('empty');
            }
        }

        shopFilter.find("input[name^='filter-']").each(function() {
           $(this).on('click', function (event) {
               if($(this).prop("checked") == true) {
                   shopFilter.find("input[name^='subfilter" + $(this).val() + "-']").each(function() {
                       $(this).prop("checked", true)
                   });
               } else if($(this).prop("checked") == false) {
                   shopFilter.find("input[name^='subfilter" + $(this).val() + "-']").each(function() {
                       $(this).prop("checked", false)
                   });
               }
            });
        });

        shopFilter.find("input[name^='subfilter']").each(function() {
            $(this).on('click', function (event) {
                var catid = $(this).data('catid');
                var allchecked = true;
                var someunchecked = false;
                shopFilter.find("input[name^='subfilter" + catid + "-']").each(function() {
                   if($(this).prop("checked") == false) {
                       allchecked = false;
                       someunchecked = true;
                   }
                });
                if (allchecked) {
                    shopFilter.find("input[name='filter-" + catid + "']").prop("checked", true)
                }
                if (someunchecked) {
                    shopFilter.find("input[name='filter-" + catid + "']").prop("checked", false)
                }
            });
        });

        var applySearchFilterBtn = $('.apply-searchfilter');
        var clearSearchFilterBtn = $('.clear-searchfilter');

        if (applySearchFilterBtn) {
            applySearchFilterBtn.on('click', function (event) {
                event.preventDefault();

                var fldno = 0;
                var mapForm = $('.searchfilter-data-form');

                cartList.children('li:not(.deleted)').each(function () {
                    var singleQuantity = Number($(this).find('.quantity').find('select').val());
                    var price = singleQuantity * Number($(this).find('.price').data('price'));
                    var product_id = Number($(this).find('.price').data('productid'));
                    var product_model = $(this).find('.price').data('productmodel');
                    fldno += 1;
                    mapForm.append('<input type="hidden" name="qty_'+ fldno + '" id="qty_' + fldno + '" value="' + String(singleQuantity) + '" />');
                    mapForm.append('<input type="hidden" name="product_'+ fldno + '" id="product_' + fldno + '" value="' + String(product_id) + '" />');
                    mapForm.append('<input type="hidden" name="price_'+ fldno + '" id="price_' + fldno + '" value="' + String(price) + '" />');
                    mapForm.append('<input type="hidden" name="model_'+ fldno + '" id="model_' + fldno + '" value="' + product_model + '" />');
                });
                mapForm.append('<input type="hidden" name="items" id="items" value="' + String(fldno) + '" />');
                $('body').append(mapForm);
                mapForm.submit();
            });
        }

        if (clearSearchFilterBtn) {
            clearSearchFilterBtn.on('click', function (event) {
                event.preventDefault();

                var fldno = 0;
                var mapForm = $('.searchfilter-data-form');

                shopFilter.find("input[name='filter_search']").val('');

                shopFilter.find("input[name^='subfilter']").each(function() {
                    $(this).prop("checked", false)
                });

                shopFilter.find("input[name^='filter-']").each(function() {
                    $(this).prop("checked", false)
                });

                cartList.children('li:not(.deleted)').each(function () {
                    var singleQuantity = Number($(this).find('.quantity').find('select').val());
                    var price = singleQuantity * Number($(this).find('.price').data('price'));
                    var product_id = Number($(this).find('.price').data('productid'));
                    var product_model = $(this).find('.price').data('productmodel');
                    fldno += 1;
                    mapForm.append('<input type="hidden" name="qty_'+ fldno + '" id="qty_' + fldno + '" value="' + String(singleQuantity) + '" />');
                    mapForm.append('<input type="hidden" name="product_'+ fldno + '" id="product_' + fldno + '" value="' + String(product_id) + '" />');
                    mapForm.append('<input type="hidden" name="price_'+ fldno + '" id="price_' + fldno + '" value="' + String(price) + '" />');
                    mapForm.append('<input type="hidden" name="model_'+ fldno + '" id="model_' + fldno + '" value="' + String(product_model) + '" />');
                });
                mapForm.append('<input type="hidden" name="items" id="items" value="' + String(fldno) + '" />');
                $('body').append(mapForm);
                mapForm.submit();
            });
        }

        function convertFloat(v) {
            v = v.toString().replace(",", "@").replace(".", ",").replace("@", ".");
            return v
        }

        function toggleCart(bool) {
            var cartIsOpen = ( typeof bool === 'undefined' ) ? cartWrapper.hasClass('cart-open') : bool;

            if (cartIsOpen) {
                cartWrapper.removeClass('cart-open');
                //reset undo
                clearInterval(undoTimeoutId);
                undo.removeClass('visible');
                cartList.find('.deleted').remove();

                setTimeout(function () {
                    cartBody.scrollTop(0);
                    //check if cart empty to hide it
                    if (Number(cartCount.find('li').eq(0).text()) == 0) cartWrapper.addClass('empty');
                }, 500);
            } else {
                cartWrapper.addClass('cart-open');
            }
        }

        function addToCart(trigger) {
            var cartIsEmpty = cartWrapper.hasClass('empty');
            //update cart product list
            addProduct(trigger.data('productid'),
                       trigger.data('productmodel'),
                       parseFloat(trigger.data('price')),
                       trigger.data('product'),
                       trigger.data('producturl'));
            //update number of items
            updateCartCount(cartIsEmpty);
            //update total price
            updateCartTotal(parseFloat(trigger.data('price')), true);
            //show cart
            cartWrapper.removeClass('empty');
        }

        function addProduct(product_id, product_model, product_price, product_name, product_url) {
            //this is just a product placeholder
            //you should insert an item with the selected product info
            //replace productId, productName, price and url with your real product info
            productId = productId + 1;
            var price = convertFloat(Number(product_price).toFixed(2));
            var productAdded = $('<li class="product"><div class="product-image"><a href="' + product_url + '"><img src="/shop/product/picture/' + product_model + '/' + product_id + '/default/small" alt="' + product_name + '"></a></div><div class="product-details"><h3><a href="' + product_url + '">' + product_name + '</a></h3><span class="price" data-price="' + product_price + '" data-productid="' + product_id + '" data-productmodel="' + product_model + '">€ ' + price + '</span><div class="actions"><a href="#0" class="delete-item">Verwijderen</a><div class="quantity"><label for="cd-product-' + productId + '">Aantal</label><span class="select"><select id="cd-product-' + productId + '" name="quantity"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option><option value="7">7</option><option value="8">8</option><option value="9">9</option></select></span></div></div></div></li>');
            cartList.prepend(productAdded);
        }

        function removeProduct(product) {
            clearInterval(undoTimeoutId);
            cartList.find('.deleted').remove();

            var topPosition = product.offset().top - cartBody.children('ul').offset().top,
                productQuantity = Number(product.find('.quantity').find('select').val()),
                productTotPrice = Number(product.find('.price').data('price')) * productQuantity;

            product.css('top', topPosition + 'px').addClass('deleted');

            //update items count + total price
            updateCartTotal(productTotPrice, false);
            updateCartCount(true, -productQuantity);
            undo.addClass('visible');

            //wait 8sec before completely remove the item
            undoTimeoutId = setTimeout(function () {
                undo.removeClass('visible');
                cartList.find('.deleted').remove();
            }, 8000);
        }

        function quickUpdateCart() {
            var quantity = 0;
            var price = 0;

            cartList.children('li:not(.deleted)').each(function () {
                var singleQuantity = Number($(this).find('select').val());
                quantity = quantity + singleQuantity;
                price = price + singleQuantity * Number($(this).find('.price').data('price'));
            });

            cartTotal.data('total', price);
            cartTotal.text(convertFloat(price.toFixed(2)));
            cartCount.find('li').eq(0).text(quantity);
            cartCount.find('li').eq(1).text(quantity + 1);
        }

        function updateCartCount(emptyCart, quantity) {
            if (typeof quantity === 'undefined') {
                var actual = Number(cartCount.find('li').eq(0).text()) + 1;
                var next = actual + 1;

                if (emptyCart) {
                    cartCount.find('li').eq(0).text(actual);
                    cartCount.find('li').eq(1).text(next);
                } else {
                    cartCount.addClass('update-count');

                    setTimeout(function () {
                        cartCount.find('li').eq(0).text(actual);
                    }, 150);

                    setTimeout(function () {
                        cartCount.removeClass('update-count');
                    }, 200);

                    setTimeout(function () {
                        cartCount.find('li').eq(1).text(next);
                    }, 230);
                }
            } else {
                var actual = Number(cartCount.find('li').eq(0).text()) + quantity;
                var next = actual + 1;

                cartCount.find('li').eq(0).text(actual);
                cartCount.find('li').eq(1).text(next);
            }
        }

        function updateCartTotal(price, add_price) {
            if (add_price) {
                cartTotal.data('total', cartTotal.data('total') + price);
            } else {
                cartTotal.data('total', cartTotal.data('total') - price);
            }
            cartTotal.text(convertFloat(cartTotal.data('total').toFixed(2)))
        }

        function synchronizeCart() {

            var data_to_sync = {}
            var fldno = 0;
            cartList.children('li:not(.deleted)').each(function () {
                var singleQuantity = Number($(this).find('.quantity').find('select').val());
                var price = singleQuantity * Number($(this).find('.price').data('price'));
                var product_id = Number($(this).find('.price').data('productid'));
                var product_model = $(this).find('.price').data('productmodel');
                fldno += 1;
                data_to_sync['qty_'+ fldno] = String(singleQuantity);
                data_to_sync['product_'+ fldno] = String(product_id);
                data_to_sync['price_'+ fldno]= String(price);
                data_to_sync['model_'+ fldno] = product_model;
            });
            data_to_sync['items'] = fldno;

            $.ajax({
                type: 'POST',
                url: '/shop/sync_cart',
                data: data_to_sync,
                cache: false,
                dataType: 'json'
            }).done(function(result) {

            }).fail(function(error) {
                console.log(error);
            });
        }

        // Product picture effects, popup big picture when user clicks on it
        // Get the modal
        var modalPopup = document.getElementById('pdmodal');

        // Get the image and insert it inside the modal - use its "alt" text as a caption
        var modalImg = document.getElementById("imgcontent");

        // When the user clicks on the picture, close the modal
        modalImg.onclick = function () {
            modalPopup.style.display = "none";
        }

        var captionText = document.getElementById("pdcaption");

        var images = document.getElementsByClassName("pdimage");
        for (var i = 0; i < images.length; i++) {
            var img = images[i];

            img.onclick = function () {
                modalPopup.style.display = "block";
                modalImg.src = this.src.replace(/^(?:\/\/|[^\/]+)*\//, "/");
                captionText.innerHTML = this.alt;
            }
        }

        // Get the <span> element that closes the modal
        var span = document.getElementsByClassName("pdclose")[0];

        // When the user clicks on <span> (x), close the modal
        span.onclick = function () {
            modalPopup.style.display = "none";
        }
    })
});