from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in directly after signing up
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
        
    return render(request, 'registration/signup.html', {'form': form})
