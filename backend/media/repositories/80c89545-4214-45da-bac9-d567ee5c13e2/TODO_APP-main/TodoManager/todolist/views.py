from django.shortcuts import render, redirect
from todolist.models import Task
from todolist.forms import TaskForm
from django.contrib import messages
from django.core.paginator import Paginator
# from django.http import HttpResponse, JsonResponse
# Create your views here.

def homepage(request):
    context ={
        'page': 'homepage'
    }
    return render(request, "main.html", context)
    

def todolist(request):
    if request.method == "POST":
        form_data =TaskForm(request.POST or None)
        if form_data.is_valid():
            form_data.save()
            messages.success(request, "Task Added Successfully")
            return redirect("todolist") 
        messages.success(request, "Something Went Wrong")

    all_tasks = Task.objects.all()
    paginator = Paginator(all_tasks, 8)
    page = request.GET.get("page")

    all_tasks = paginator.get_page(page)
    context ={
        'page': 'todolist',
        'all_tasks': all_tasks
     }
    return render(request, "todolist.html", context)


def delete_task(request, task_id):
    task_obj = Task.objects.get(id = task_id)
    task_obj.delete()
    messages.success(request,  f"Task- {task_obj.task} deleted.")
    return redirect("todolist")


def edit_task(request, task_id):
    task_obj = Task.objects.get(id= task_id)

    if request.method == "POST":
        form_data =TaskForm(request.POST or None, instance = task_obj)
        if form_data.is_valid():
            form_data.save()
            messages.success(request, "Task Updated Successfully")
            return redirect("todolist")
        messages.success(request, "Error Encountered in updation")
    else:
        context={
        'task_obj': task_obj
        }
        return render(request, "edit.html", context)

def complete_task(request, task_id):
    task_obj = Task.objects.get(id= task_id)
    task_obj.isCompleted = True
    task_obj.save()
    messages.success(request, "Status Changed Successfully")
    return redirect("todolist")


def pending_task(request, task_id):
    task_obj = Task.objects.get(id= task_id)
    task_obj.isCompleted = False
    task_obj.save()
    messages.success(request, "Status Changed Successfully")
    return redirect("todolist")


def contact(request):
    context ={
        'page': 'contact'
    }
    return render(request, "contact.html", context)

def about(request):
    context ={
        'page': 'about'
    }
    return render(request, "about.html", context)

