async def command_gimme(ctx: commands.Context, request: tuple):
    """
    Called whenever a user whispers the bot to get the noted messages.\n
    ctx: The context in which the message was sent.\n
    request: The tuple containing all of the pertinant request information.\n
    Must be in one of the following formats:\n
    <user/all> \\<guild> \\<between> \\<date1> \\<date2>\n
    <user/all> \\<guild> \\<before/after> \\<date1>\n
    <user/all> \\<guild> \\<latest> \\<date1>\n
    All dates must be in either the YYYY/MM/DD or YYYY/MM/DD HH:MM:SS format.
    """

    # Get the user requesting the information.
    requesting_user=ctx.author.id

    # Break down the tuple into more easily managed bits.
    user=request[0]
    guild=request[1]
    request_range=request[2]
    date1=""
    date2=""

    if (request_range.lower()!="all" and request_range.lower()!="latest" and 
        request_range.lower()!="between" and request_range.lower()!="before" and
        request_range.lower()!="after"):
        await ctx.send("The range you sent was invalid. It must be one of the "+
                       "following: \'before\', \'after\', \'between\', "+
                       "\'latest\', or \'all\' without the single quotes.")
        return

    # Check if the range is "between", "before", or "after"
    if request_range.lower()!="all" and request_range.lower()!="latest":
        # Try to use the first date as it is.
        try:
            date1=datetime.strptime(request[3],time_format)
        except ValueError:
            # If it isn't currently in the precise format, try to make it so.
            try:
                date1=datetime.strptime(request[3],"%Y/%m/%d")
                date1=date1.replace(hour=00,minute=00,second=00)
            except ValueError:
                # If the value cannot be converted, let the requester know.
                await ctx.send("Error. Please enter the dates in either a "+
                            "\"yyyy/mm/dd\" or \"yyyy/mm/dd hh/mm/ss\" format "+
                            "without the quotes.")
                return

        # If the length is 5, check the second date.
        if len(request)==5:
            try:
                # Try to use the second date as it is.
                date2=datetime.strptime(request[4],time_format)
            except ValueError:
                # If it isn't currently in the precise format try to make it so.
                try:
                    date2=datetime.strptime(request[4],"%Y/%m/%d")
                    date2=date2.replace(hour=23,minute=59,second=59)
                except ValueError:
                    # If the value cannot be converted, let the requester know.
                    await ctx.send("Error. Please enter the dates in either a "+
                                "\"YYYY/MM/DD\" or \"YYYY/MM/DD HH:MM:SS\" "+
                                "format, without the quotes.")
                    return

    # If the range is "latest"
    elif request_range.lower()=="latest":
        # Then date1 will actuallly be an integer with the number of messages to
        # get.
        date1=int(request[3])

    cursor=mydb.cursor()

    # Check if the guild is given as an ID.
    try:
        guild=int(guild)
    except ValueError:
        # If it isn't, get the guildID from the guildList.
        cursor.execute("USE guildList")
        sql="SELECT guildID FROM Guilds WHERE guildName=%s"
        cursor.execute(sql,(guild,))
        guild=cursor.fetchall()
        if len(guild)==0:
            await ctx.send(f"Sorry, I could not find the {request[1]} server "+
                           "in my database. Please double check that it's "+
                           "spelled correctly.")
            return
        else:
            guild=guild[0][0]

    # Use the guild.
    cursor.execute(f"USE server{guild}")

    # Check to see if the requesting user is a current or former member of this
    # guild.
    cursor.execute("SELECT memberID FROM Members WHERE memberID="+
                   f"{requesting_user}")
    requesting_user=cursor.fetchall()

    # If they are not either a current or previous member of a guild.
    if len(requesting_user)==0:
        # Let them know that they can't request that information.
        await ctx.send("You must be either a current or former member of the "+
                       "guild that you are trying to get messages from.")
        return

    # Build the initial SQL statement.
    sql=("SELECT messageID,Channels.channelName,authorID,"+
         "CONCAT(Members.memberName,'#',Members.discriminator),dateCreated,"+
         "dateEdited,dateDeleted,message,filename,url FROM Messages "+
	    "LEFT JOIN Channels ON (Messages.channelID=Channels.channelID) "+
	    "LEFT JOIN Members ON (Messages.authorID=Members.memberID) ")

    # If there is some sort of limiting factor, add "WHERE".
    if str(user).lower()!="all" or isinstance(date1,datetime):
        sql+="WHERE "

    # Check if the user is given as an ID.
    try:
        user=int(user)
    except ValueError:
        # If it isn't, get the user's ID from the Members table.
        if user.lower()!="all":
            user=user.split("#")
            user[1]=int(user[1])
            get_user=("SELECT memberID FROM Members where memberName=%s AND "+
                "discriminator=%s")
            cursor.execute(get_user,user)
            user=cursor.fetchall()
            if len(user)==0:
                await ctx.send(f"Sorry, I could not find user {request[0]} in "+
                               f"{request[1]}. Either the name was misspelled "+
                               "or they are not in this server.")
                return
            else:
                user=user[0][0]
                sql+="authorID=%s "
    
    # If The first date is an actual date (as opposed to being an integer) and
    # the user is a userID (as opposed to the string "all"), then append "AND"
    if isinstance(date1,datetime) and isinstance(user,int):
        sql+="AND "
    
    # If the first date is instead an integer, then set the limiting.
    elif isinstance(date1,int):
        sql+= "ORDER BY dateCreated DESC LIMIT %s"

    # If the range is "between", then set the ranges.
    if request_range.lower()=="between":
        sql+=("dateCreated BETWEEN CAST(%s AS DATETIME) AND "+
                 "CAST(%s AS DATETIME)")
    
    # If the range is "before", set the range to be less than the set date.
    elif request_range.lower()=="before":
        sql+="dateCreated <= %s"
        date1=date1.replace(hour=23,minute=59,second=59)
    
    # If the range is "after", set the range to be greater than the set date.
    elif request_range.lower()=="after":
        sql=sql+"dateCreated >= %s"

    # If the length is 5.
    if len(request)==5:
        # and the user is a number (as opposed to "all").
        if isinstance(user,int):
            cursor.execute(sql,(user,date1,date2))
        # If the user is "all".
        else:
            cursor.execute(sql,(date1,date2))

    # If the length is 4.
    elif len(request)==4:
        # and the user is a number (as opposed to "all").
        if isinstance(user,int):
            cursor.execute(sql,(user,date1))            
        # If the user is "all".
        else:
            cursor.execute(sql,(date1,))
    
    # If the length is anything else, just execute the command as it is.
    else:
        cursor.execute(sql)

    # Get all of the records.
    message_records=cursor.fetchall()

    # Instantiate the workbook so the data can be exported as an Excel doc.
    test_workbook=xlwt.Workbook()

    # Add a worksheet.
    test_worksheet=test_workbook.add_sheet("output")
    
    # Set hte date format for the dates.
    date_format=xlwt.easyxf(num_format_str="YYYY/MM/DD HH:MM:SS")
    
    # Set the top rows so it's easy to distinguish which column is which/
    test_worksheet.write(0,0,"Message ID")
    test_worksheet.write(0,1,"Channel Name")
    test_worksheet.write(0,2,"Author ID")
    test_worksheet.write(0,3,"Author Name")
    test_worksheet.write(0,4,"Date Created")
    test_worksheet.write(0,5,"Date Edited")
    test_worksheet.write(0,6,"Date Deleted")
    test_worksheet.write(0,7,"Message")
    test_worksheet.write(0,8,"Filename")
    test_worksheet.write(0,9,"URL")

    # Begin counting rows.
    row=1
    
    # Go through each record returned and write them to the appropriate column.
    for record in message_records:
        test_worksheet.write(row,0,str(record[0]))
        test_worksheet.write(row,1,record[1])
        test_worksheet.write(row,2,str(record[2]))
        test_worksheet.write(row,3,record[3])
        test_worksheet.write(row,4,record[4],date_format)
        test_worksheet.write(row,5,record[5],date_format)
        test_worksheet.write(row,6,record[6],date_format)
        test_worksheet.write(row,7,record[7])
        test_worksheet.write(row,8,record[8])
        test_worksheet.write(row,9,record[9])
        row+=1

    # Build an appropriate name for the file.
    workbook_name = str(user)

    # Append the guild and the range.
    workbook_name+="_from_"+str(guild)+"_"+request_range+"_"

    # If the range is "between".
    if request_range.lower()=="between":
        # Append both of the dates.
        workbook_name+=str(date1)+"_and_"+str(date2)+".xls"
    
    # If it's anything else.
    else:
        # Append the date or number.
        workbook_name+=str(date1)+".xls"

    # Replace the colons from the datetime and make them hyphens so the text is
    # appropriate for a filename.
    workbook_name=str(workbook_name).replace(":","-")

    # Save the output.
    test_workbook.save(workbook_name)

    # Load the file as a Discord File.
    discord_file=discord.File(workbook_name)

    # Send the file to the user from the given context.
    await ctx.send(content="Here's the content you requested!",
                   file=discord_file)

    # Delete the file from the hard drive.
    os.remove(workbook_name)