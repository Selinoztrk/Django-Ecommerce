from django.shortcuts import render, redirect
from cart.cart import Cart
from payment.forms import ShippingForm, PaymentForm
from payment.models import ShippingAddress, Order, OrderItem
from django.contrib.auth.models import User
from django.contrib import messages
from store.models import Product, Profile
import datetime
# Stripe imports
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


stripe.api_key = settings.STRIPE_SECRET_KEY


def payment_success(request):
    return render(request, 'payment/payment_success.html', {})


def payment_cancel(request):
    return render(request, 'payment/payment_cancel.html', {})


def checkout(request):
    # Get the cart
    cart = Cart(request)
    cart_products = cart.get_prods
    quantities = cart.get_quants
    totals = cart.cart_total()

    if request.user.is_authenticated:
        # Checkout as logged in user
        shipping_user = ShippingAddress.objects.get(user__id=request.user.id) # Shipping User
        shipping_form = ShippingForm(request.POST, instance=shipping_user) # Shipping Form
        return render(request, "payment/checkout.html", 
                      {"cart_products":cart_products, "quantities":quantities, "totals":totals, "shipping_form":shipping_form})
    else:
        # Checkout as guest
        shipping_form = ShippingForm(request.POST)
        return render(request, "payment/checkout.html", 
                      {"cart_products":cart_products, "quantities":quantities, "totals":totals, "shipping_form":shipping_form})


@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        try:
            cart = Cart(request)
            cart_products = cart.get_prods()
            quantities = cart.get_quants()
            line_items = []

            for product in cart_products:
                quantity = quantities.get(str(product.id), 1)
                price = product.sale_price if product.is_sale else product.price
                line_items.append({
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': product.name,
                        },
                        'unit_amount': int(price * 100),
                    },
                    'quantity': quantity,
                })

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url='http://django-ecommerce-production-96f5.up.railway.app/payment/payment_success/',
                cancel_url='http://django-ecommerce-production-96f5.up.railway.app/payment/payment_cancel/',
            )
            return JsonResponse({'id': session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


def billing_info(request):
    if request.POST:
        # Get the cart
        cart = Cart(request)
        cart_products = cart.get_prods
        quantities = cart.get_quants
        totals = cart.cart_total()

        # Create a session with Shipping Info
        my_shipping = request.POST
        request.session['my_shipping'] = my_shipping

        # Stripe Key
        stripe_publishable_key = settings.STRIPE_PUBLISHABLE_KEY

        # Check to see if user is logged in
        if request.user.is_authenticated:
            billing_form = PaymentForm()
            return render(request, "payment/billing_info.html", 
                        {
                            "cart_products": cart_products,
                            "quantities": quantities,
                            "totals": totals,
                            "shipping_info": request.POST,
                            "billing_form": billing_form,
                            "stripe_pub_key": settings.STRIPE_PUBLISHABLE_KEY
                        })
        else:
            billing_form = PaymentForm()
            return render(request, "payment/billing_info.html", 
                        {
                            "cart_products": cart_products,
                            "quantities": quantities,
                            "totals": totals,
                            "shipping_info": request.POST,
                            "billing_form": billing_form,
                            "stripe_pub_key": settings.STRIPE_PUBLISHABLE_KEY
                        })

    else:
        messages.success(request, "Access Denied")
        return redirect('home')


def process_order(request):
    if request.POST:
        # Get the cart
        cart = Cart(request)
        cart_products = cart.get_prods
        quantities = cart.get_quants
        totals = cart.cart_total()

        # Get Billing Info from the last page 
        payment_form = PaymentForm(request.POST or None)
        # Get Shipping Session Data
        my_shipping = request.session.get('my_shipping')

        # Gather Order Info
        full_name = my_shipping['shipping_full_name']
        email = my_shipping['shipping_email']

        # Create Shipping Address from Session Info
        shipping_address = f"{my_shipping['shipping_address1']}\n{my_shipping['shipping_address2']}\n{my_shipping['shipping_city']}\n{my_shipping['shipping_state']}\n{my_shipping['shipping_zipcode']}\n{my_shipping['shipping_country']}"
        amount_paid = totals

        # Create an Order
        if request.user.is_authenticated:
            user = request.user  # logged in
            # Create Order
            create_order = Order(user=user, full_name=full_name, email=email, shipping_address=shipping_address, amount_paid=amount_paid)
            create_order.save()

            # Add Order Items
            order_id = create_order.pk # Get the Order ID

            # Get Product Info
            for product in cart_products():
                product_id = product.id # Get Product ID

                # Get the Product Price
                if product.is_sale:
                    price = product.sale_price
                else:
                    price = product.price
                
                # Get quantity
                for key,value in quantities().items():
                    if int(key) == product.id:
                        # Create order item
                        create_order_item = OrderItem(order_id=order_id, product_id=product_id, user=user, quantity=value, price=price)
                        create_order_item.save()

            # Delete our cart
            for key in list(request.session.keys()):
                if key == "session_key":
                    # Delete the key
                    del request.session[key]

            # Delete Cart from Database (old_cart field)
            current_user = Profile.objects.filter(user__id=request.user.id)
            # Delete shopping cart in Database (old_cart field)
            current_user.update(old_cart="")

            messages.success(request, "Order Placed!")
            return redirect('home')
        
        else:
            # not logged in 
            # Create Order
            create_order = Order(full_name=full_name, email=email, shipping_address=shipping_address, amount_paid=amount_paid)
            create_order.save()

            # Add Order Items
            order_id = create_order.pk # Get the Order ID

            # Get Product Info
            for product in cart_products():
                product_id = product.id # Get Product ID

                # Get the Product Price
                if product.is_sale:
                    price = product.sale_price
                else:
                    price = product.price
                
                # Get quantity
                for key,value in quantities().items():
                    if int(key) == product.id:
                        # Create order item
                        create_order_item = OrderItem(order_id=order_id, product_id=product_id, quantity=value, price=price)
                        create_order_item.save()
            
            # Delete our cart
            for key in list(request.session.keys()):
                if key == "session_key":
                    # Delete the key
                    del request.session[key]

            messages.success(request, "Order Placed!")
            return redirect('home')
    
    else:
        messages.success(request, "Access Denied!")
        return redirect('home')


def not_shipped_dash(request):
    if request.user.is_authenticated and request.user.is_superuser:
        orders = Order.objects.filter(shipped=False)
        
        if request.POST:
            status = request.POST['shipping_status']
            num = request.POST['num']
            # Get the Order
            order = Order.objects.filter(id=num)

            # Grab Date and Time
            now = datetime.datetime.now()
            # Update Order
            order.update(shipped=True, date_shipped=now)
            # Redirect
            messages.success(request, "Shipping Status Updated")
            return redirect('home')
        
        return render(request, "payment/not_shipped_dash.html", {"orders":orders})
    else:
        messages.success(request, "Access Denied!")
        return redirect('home')


def shipped_dash(request):
    if request.user.is_authenticated and request.user.is_superuser:
        orders = Order.objects.filter(shipped=True)

        if request.POST:
            status = request.POST['shipping_status']
            num = request.POST['num']
            # Get the Order
            order = Order.objects.filter(id=num)

            # Grab Date and Time
            now = datetime.datetime.now()
            # Update Order
            order.update(shipped=False)
            # Redirect
            messages.success(request, "Shipping Status Updated")
            return redirect('home')
        
        return render(request, "payment/shipped_dash.html", {"orders":orders})
    else:
        messages.success(request, "Access Denied!")
        return redirect('home')


def orders(request, pk):
    if request.user.is_authenticated and request.user.is_superuser:
        # Get the Order
        order = Order.objects.get(id=pk)
        # Get the Order Items
        items = OrderItem.objects.filter(order=pk)

        if request.POST:
            status = request.POST['shipping_status']
            # Check if true or false
            if status == "true":
                # Get the Order
                order = Order.objects.filter(id=pk)
                # Update the status
                now = datetime.datetime.now()
                order.update(shipped=True, date_shipped=now)
            else:
                # Get the Order
                order = Order.objects.filter(id=pk)
                # Update the status
                order.update(shipped=False)
            messages.success(request, "Shipping Status Updated")
            return redirect('home')

        return render(request, 'payment/orders.html', {"order":order, "items":items})
    else:
        messages.success(request, "Access Denied!")
        return redirect('home')