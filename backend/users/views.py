from django.shortcuts import render, redirect
from django.contrib.auth import login, get_user_model
from django.contrib import messages

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not all([name, email, password, confirm_password]):
            messages.error(request, "All fields are required.")
        elif password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif get_user_model().objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
        else:
            # We use email as the username since username is required by default User model
            first_name = name.split(' ')[0]
            last_name = ' '.join(name.split(' ')[1:]) if ' ' in name else ''
            
            user = get_user_model().objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            login(request, user, backend='users.backends.EmailBackend')
            return redirect('dashboard')
            
    return render(request, 'registration/signup.html')
